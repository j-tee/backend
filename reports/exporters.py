from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Dict, Iterable, List, Tuple

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from docx import Document
from docx.shared import Inches
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .services.inventory import InventoryReportRow


class BaseReportExporter(ABC):
    content_type: str
    file_extension: str

    @abstractmethod
    def export(self, report_data: Dict[str, Any]) -> bytes:  # pragma: no cover - interface
        raise NotImplementedError


class ExcelReportExporter(BaseReportExporter):
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    file_extension = 'xlsx'

    def export(self, report_data: Dict[str, Any]) -> bytes:
        workbook = Workbook()
        summary_sheet = workbook.active
        summary_sheet.title = 'Summary'

        summary_sheet.append(['Inventory Valuation Report'])
        summary_sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
        summary_sheet['A1'].font = Font(size=14, bold=True)

        summary_sheet.append(['Generated At', report_data['generated_at'].strftime('%Y-%m-%d %H:%M:%S %Z')])
        if report_data.get('filters'):
            for key, value in report_data['filters'].items():
                summary_sheet.append([key.replace('_', ' ').title(), str(value)])
        summary_sheet.append([])

        summary_sheet.append(['Metric', 'Value'])
        for metric, value in report_data['summary'].items():
            label = metric.replace('_', ' ').title()
            summary_sheet.append([label, value])

        detail_sheet = workbook.create_sheet(title='Inventory Detail')
        detail_sheet.append(report_data['detail_headers'])

        for row in report_data['rows']:
            detail_sheet.append(row.as_list())

        self._auto_fit_columns([summary_sheet, detail_sheet])

        with BytesIO() as output:
            workbook.save(output)
            return output.getvalue()

    @staticmethod
    def _auto_fit_columns(sheets: Iterable[Any]) -> None:
        for sheet in sheets:
            for column_cells in sheet.columns:
                max_length = 0
                column = get_column_letter(column_cells[0].column)
                for cell in column_cells:
                    try:
                        cell_value = str(cell.value) if cell.value is not None else ''
                    except ValueError:
                        cell_value = ''
                    max_length = max(max_length, len(cell_value))
                adjusted_width = max_length + 2
                sheet.column_dimensions[column].width = min(adjusted_width, 50)


class WordReportExporter(BaseReportExporter):
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    file_extension = 'docx'

    def export(self, report_data: Dict[str, Any]) -> bytes:
        document = Document()
        document.add_heading('Inventory Valuation Report', level=1)
        document.add_paragraph(f"Generated at: {report_data['generated_at'].strftime('%Y-%m-%d %H:%M:%S %Z')}")

        if report_data.get('filters'):
            document.add_heading('Filters', level=2)
            for key, value in report_data['filters'].items():
                document.add_paragraph(f"{key.replace('_', ' ').title()}: {value}", style='List Bullet')

        document.add_heading('Summary', level=2)
        for metric, value in report_data['summary'].items():
            document.add_paragraph(f"{metric.replace('_', ' ').title()}: {value}")

        document.add_heading('Inventory Detail', level=2)
        table = document.add_table(rows=1, cols=len(report_data['detail_headers']))
        header_cells = table.rows[0].cells
        for idx, header in enumerate(report_data['detail_headers']):
            header_cells[idx].text = header

        max_rows = 200  # prevent overly large documents
        for idx, row in enumerate(report_data['rows']):
            if idx >= max_rows:
                break
            cells = table.add_row().cells
            for cell_idx, value in enumerate(row.as_list()):
                cells[cell_idx].text = str(value)

        document.add_paragraph()
        document.add_paragraph('Note: Detail view trimmed to first 200 rows for readability.')

        with BytesIO() as output:
            document.save(output)
            return output.getvalue()


class PDFReportExporter(BaseReportExporter):
    content_type = 'application/pdf'
    file_extension = 'pdf'

    def export(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        story: List[Any] = []
        story.append(Paragraph('Inventory Valuation Report', styles['Title']))
        story.append(Paragraph(f"Generated at: {report_data['generated_at'].strftime('%Y-%m-%d %H:%M:%S %Z')}", styles['Normal']))
        story.append(Spacer(1, 12))

        if report_data.get('filters'):
            story.append(Paragraph('Filters', styles['Heading2']))
            for key, value in report_data['filters'].items():
                story.append(Paragraph(f"• {key.replace('_', ' ').title()}: {value}", styles['Normal']))
            story.append(Spacer(1, 12))

        summary_table_data = [['Metric', 'Value']]
        for metric, value in report_data['summary'].items():
            summary_table_data.append([metric.replace('_', ' ').title(), str(value)])
        summary_table = Table(summary_table_data, hAlign='LEFT')
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 18))

        detail_table_data = [report_data['detail_headers']]
        max_rows = 60
        for idx, row in enumerate(report_data['rows']):
            if idx >= max_rows:
                break
            detail_table_data.append([str(value) for value in row.as_list()])
        detail_table = Table(detail_table_data, repeatRows=1)
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        story.append(detail_table)
        if len(report_data['rows']) > max_rows:
            story.append(Spacer(1, 12))
            story.append(Paragraph('Detail view trimmed to first 60 rows for PDF output.', styles['Italic']))

        doc.build(story)
        buffer.seek(0)
        return buffer.read()


EXPORTER_MAP = {
    'excel': ExcelReportExporter,
    'docx': WordReportExporter,
    'pdf': PDFReportExporter,
}
