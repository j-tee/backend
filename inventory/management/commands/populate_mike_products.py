from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User, Business
from inventory.models import Category, Product


CATEGORY_DESCRIPTIONS = {
    "Electrical Cables": "Low voltage, armoured, and communication cables for residential and commercial wiring projects.",
    "Lighting & Bulbs": "Indoor and outdoor lighting solutions including bulbs, panels, and floodlights.",
    "Circuit Protection": "Breakers, boards, and devices that keep electrical systems safe from overloads and surges.",
    "Switches & Sockets": "Wall switches, sockets, and power outlets for distribution points and customer access.",
    "Electrical Accessories": "Supporting hardware and consumables required for installations and maintenance.",
}

PRODUCT_CATALOGUE = [
    {"sku": "ELEC-0001", "name": "1.5mm House Wire Red 100m", "category": "Electrical Cables", "unit": "roll", "retail_price": "420.00", "wholesale_price": "360.00", "cost": "295.00"},
    {"sku": "ELEC-0002", "name": "1.5mm House Wire Blue 100m", "category": "Electrical Cables", "unit": "roll", "retail_price": "420.00", "wholesale_price": "360.00", "cost": "295.00"},
    {"sku": "ELEC-0003", "name": "2.5mm House Wire Red 100m", "category": "Electrical Cables", "unit": "roll", "retail_price": "560.00", "wholesale_price": "490.00", "cost": "410.00"},
    {"sku": "ELEC-0004", "name": "2.5mm House Wire Blue 100m", "category": "Electrical Cables", "unit": "roll", "retail_price": "560.00", "wholesale_price": "490.00", "cost": "410.00"},
    {"sku": "ELEC-0005", "name": "4mm Twisted Cable 100m", "category": "Electrical Cables", "unit": "roll", "retail_price": "780.00", "wholesale_price": "690.00", "cost": "580.00"},
    {"sku": "ELEC-0006", "name": "6mm Armoured Cable 50m", "category": "Electrical Cables", "unit": "coil", "retail_price": "860.00", "wholesale_price": "790.00", "cost": "640.00"},
    {"sku": "ELEC-0007", "name": "10mm Armoured Cable 50m", "category": "Electrical Cables", "unit": "coil", "retail_price": "1250.00", "wholesale_price": "1120.00", "cost": "930.00"},
    {"sku": "ELEC-0008", "name": "16mm Armoured Cable 50m", "category": "Electrical Cables", "unit": "coil", "retail_price": "1690.00", "wholesale_price": "1500.00", "cost": "1260.00"},
    {"sku": "ELEC-0009", "name": "Cat6 Ethernet Cable 305m", "category": "Electrical Cables", "unit": "box", "retail_price": "1450.00", "wholesale_price": "1310.00", "cost": "1080.00"},
    {"sku": "ELEC-0010", "name": "Flexible Extension Cord 3-Core 50m", "category": "Electrical Cables", "unit": "coil", "retail_price": "520.00", "wholesale_price": "465.00", "cost": "390.00"},
    {"sku": "ELEC-0011", "name": "LED Bulb 9W Warm White", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "28.00", "wholesale_price": "22.00", "cost": "16.00"},
    {"sku": "ELEC-0012", "name": "LED Bulb 12W Daylight", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "32.00", "wholesale_price": "26.00", "cost": "19.00"},
    {"sku": "ELEC-0013", "name": "LED Tube Light 4ft", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "85.00", "wholesale_price": "70.00", "cost": "52.00"},
    {"sku": "ELEC-0014", "name": "Rechargeable Emergency Lamp", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "215.00", "wholesale_price": "190.00", "cost": "150.00"},
    {"sku": "ELEC-0015", "name": "LED Floodlight 50W", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "360.00", "wholesale_price": "315.00", "cost": "258.00"},
    {"sku": "ELEC-0016", "name": "Ceiling Panel Light 18W", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "165.00", "wholesale_price": "140.00", "cost": "110.00"},
    {"sku": "ELEC-0017", "name": "Round Downlight 7W", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "60.00", "wholesale_price": "48.00", "cost": "36.00"},
    {"sku": "ELEC-0018", "name": "Street Light 120W IP66", "category": "Lighting & Bulbs", "unit": "pcs", "retail_price": "980.00", "wholesale_price": "870.00", "cost": "710.00"},
    {"sku": "ELEC-0019", "name": "MCB 6A Single Pole", "category": "Circuit Protection", "unit": "pcs", "retail_price": "58.00", "wholesale_price": "46.00", "cost": "34.00"},
    {"sku": "ELEC-0020", "name": "MCB 10A Single Pole", "category": "Circuit Protection", "unit": "pcs", "retail_price": "58.00", "wholesale_price": "46.00", "cost": "34.00"},
    {"sku": "ELEC-0021", "name": "MCB 32A Double Pole", "category": "Circuit Protection", "unit": "pcs", "retail_price": "125.00", "wholesale_price": "105.00", "cost": "82.00"},
    {"sku": "ELEC-0022", "name": "RCCB 63A 30mA", "category": "Circuit Protection", "unit": "pcs", "retail_price": "465.00", "wholesale_price": "410.00", "cost": "328.00"},
    {"sku": "ELEC-0023", "name": "Distribution Board 12 Way", "category": "Circuit Protection", "unit": "pcs", "retail_price": "720.00", "wholesale_price": "650.00", "cost": "520.00"},
    {"sku": "ELEC-0024", "name": "Surge Protector 2P 40kA", "category": "Circuit Protection", "unit": "pcs", "retail_price": "385.00", "wholesale_price": "340.00", "cost": "270.00"},
    {"sku": "ELEC-0025", "name": "Changeover Switch 100A", "category": "Circuit Protection", "unit": "pcs", "retail_price": "910.00", "wholesale_price": "845.00", "cost": "690.00"},
    {"sku": "ELEC-0026", "name": "NH Fuse Link 100A", "category": "Circuit Protection", "unit": "pcs", "retail_price": "95.00", "wholesale_price": "80.00", "cost": "62.00"},
    {"sku": "ELEC-0027", "name": "1-Gang 1-Way Switch", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "22.00", "wholesale_price": "17.00", "cost": "12.00"},
    {"sku": "ELEC-0028", "name": "2-Gang 1-Way Switch", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "32.00", "wholesale_price": "26.00", "cost": "19.00"},
    {"sku": "ELEC-0029", "name": "3-Gang 2-Way Switch", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "48.00", "wholesale_price": "39.00", "cost": "28.00"},
    {"sku": "ELEC-0030", "name": "Door Bell Switch", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "26.00", "wholesale_price": "21.00", "cost": "15.00"},
    {"sku": "ELEC-0031", "name": "13A Double Switched Socket", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "36.00", "wholesale_price": "29.00", "cost": "21.00"},
    {"sku": "ELEC-0032", "name": "15A Industrial Socket", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "68.00", "wholesale_price": "56.00", "cost": "41.00"},
    {"sku": "ELEC-0033", "name": "USB Wall Socket Dual 2.1A", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "85.00", "wholesale_price": "72.00", "cost": "55.00"},
    {"sku": "ELEC-0034", "name": "Weatherproof Socket IP55", "category": "Switches & Sockets", "unit": "pcs", "retail_price": "145.00", "wholesale_price": "128.00", "cost": "102.00"},
    {"sku": "ELEC-0035", "name": "Cable Lug 16mm Pack of 10", "category": "Electrical Accessories", "unit": "pack", "retail_price": "38.00", "wholesale_price": "30.00", "cost": "22.00"},
    {"sku": "ELEC-0036", "name": "Cable Tie 200mm Pack of 100", "category": "Electrical Accessories", "unit": "pack", "retail_price": "48.00", "wholesale_price": "39.00", "cost": "28.00"},
    {"sku": "ELEC-0037", "name": "PVC Trunking 25mm x 3m", "category": "Electrical Accessories", "unit": "length", "retail_price": "32.00", "wholesale_price": "26.00", "cost": "19.00"},
    {"sku": "ELEC-0038", "name": "PVC Conduit Pipe 20mm x 3m", "category": "Electrical Accessories", "unit": "length", "retail_price": "28.00", "wholesale_price": "22.00", "cost": "16.00"},
    {"sku": "ELEC-0039", "name": "Junction Box 4-Way", "category": "Electrical Accessories", "unit": "pcs", "retail_price": "18.00", "wholesale_price": "14.00", "cost": "9.50"},
    {"sku": "ELEC-0040", "name": "Insulation Tape Red 20m", "category": "Electrical Accessories", "unit": "roll", "retail_price": "8.50", "wholesale_price": "6.80", "cost": "4.90"},
]


class Command(BaseCommand):
    help = "Populate ~40 electrical products for Mike Tetteh's business catalogue."

    def handle(self, *args, **options):
        try:
            owner = User.objects.get(email="mikedlt009@gmail.com")
        except User.DoesNotExist as exc:
            raise CommandError("Owner with email mikedlt009@gmail.com does not exist. Register the business owner first.") from exc

        business = Business.objects.filter(owner=owner).first()
        if business is None:
            raise CommandError("No business is linked to Mike Tetteh. Create the business record before populating products.")

        with transaction.atomic():
            categories = self._ensure_categories()
            created = 0
            updated = 0

            for product_data in PRODUCT_CATALOGUE:
                category = categories[product_data["category"]]
                defaults={
                    "name": product_data["name"],
                    "description": f"Electrical stock item supplied by {business.name}.",
                    "category": category,
                    "unit": product_data["unit"],
                    "is_active": True,
                }

                product, created_flag = Product.objects.update_or_create(
                    sku=product_data["sku"],
                    defaults=defaults,
                )

                if created_flag:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Product catalogue sync complete for {business.name}: {created} created, {updated} refreshed."
        ))

    def _ensure_categories(self):
        categories = {}
        for name, description in CATEGORY_DESCRIPTIONS.items():
            category, _ = Category.objects.get_or_create(name=name, defaults={"description": description})
            if not category.description:
                category.description = description
                category.save(update_fields=["description"])
            categories[name] = category
        return categories
