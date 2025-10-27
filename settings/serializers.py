from rest_framework import serializers
from .models import BusinessSettings


class BusinessSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for business settings.
    Validates JSON structure for each settings category.
    """

    class Meta:
        model = BusinessSettings
        fields = [
            'id',
            'business',
            'regional',
            'appearance',
            'notifications',
            'receipt',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'business', 'created_at', 'updated_at']

    def validate_regional(self, value):
        """Validate regional settings structure"""
        if 'currency' in value:
            currency = value['currency']
            required_fields = ['code', 'symbol', 'name', 'position', 'decimalPlaces']
            for field in required_fields:
                if field not in currency:
                    raise serializers.ValidationError(
                        f"Currency must include '{field}' field"
                    )

            # Validate position
            if currency['position'] not in ['before', 'after']:
                raise serializers.ValidationError(
                    "Currency position must be 'before' or 'after'"
                )

            # Validate decimal places
            if not isinstance(currency['decimalPlaces'], int) or currency['decimalPlaces'] < 0:
                raise serializers.ValidationError(
                    "decimalPlaces must be a non-negative integer"
                )

        # Validate time format
        if 'timeFormat' in value:
            if value['timeFormat'] not in ['12h', '24h']:
                raise serializers.ValidationError(
                    "timeFormat must be '12h' or '24h'"
                )

        # Validate first day of week
        if 'firstDayOfWeek' in value:
            if not isinstance(value['firstDayOfWeek'], int) or not (0 <= value['firstDayOfWeek'] <= 6):
                raise serializers.ValidationError(
                    "firstDayOfWeek must be an integer between 0 (Sunday) and 6 (Saturday)"
                )

        return value

    def validate_appearance(self, value):
        """Validate appearance settings"""
        # Validate theme preset
        valid_themes = [
            'default-blue',
            'emerald-green',
            'purple-galaxy',
            'sunset-orange',
            'ocean-teal',
            'rose-pink',
            'slate-minimal'
        ]
        if 'themePreset' in value:
            if value['themePreset'] not in valid_themes:
                raise serializers.ValidationError(
                    f"Invalid theme preset. Must be one of: {', '.join(valid_themes)}"
                )

        # Validate color scheme
        if 'colorScheme' in value:
            if value['colorScheme'] not in ['light', 'dark', 'auto']:
                raise serializers.ValidationError(
                    "colorScheme must be 'light', 'dark', or 'auto'"
                )

        # Validate font size
        if 'fontSize' in value:
            if value['fontSize'] not in ['small', 'medium', 'large']:
                raise serializers.ValidationError(
                    "fontSize must be 'small', 'medium', or 'large'"
                )

        # Validate boolean fields
        boolean_fields = ['compactMode', 'animationsEnabled', 'highContrast']
        for field in boolean_fields:
            if field in value and not isinstance(value[field], bool):
                raise serializers.ValidationError(
                    f"{field} must be a boolean value"
                )

        return value

    def validate_notifications(self, value):
        """Validate notification settings"""
        # All notification fields should be boolean
        for key, val in value.items():
            if not isinstance(val, bool):
                raise serializers.ValidationError(
                    f"{key} must be a boolean value"
                )
        return value

    def validate_receipt(self, value):
        """Validate receipt settings"""
        # Validate boolean fields
        boolean_fields = ['showLogo', 'showTaxBreakdown', 'showBarcode']
        for field in boolean_fields:
            if field in value and not isinstance(value[field], bool):
                raise serializers.ValidationError(
                    f"{field} must be a boolean value"
                )

        # Validate paper size
        valid_paper_sizes = ['thermal-80mm', 'thermal-58mm', 'a4', 'letter']
        if 'paperSize' in value:
            if value['paperSize'] not in valid_paper_sizes:
                raise serializers.ValidationError(
                    f"paperSize must be one of: {', '.join(valid_paper_sizes)}"
                )

        return value
