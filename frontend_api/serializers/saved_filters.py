from rest_framework import serializers
from profile.models import SavedFilter
from signals.models import Category, Participant


class SavedFilterSerializer(serializers.ModelSerializer):
    """
    Serializer for SavedFilter model
    Handles serialization of saved filter configurations with all filter fields
    """
    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        required=False,
        allow_null=True
    )
    participants = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Participant.objects.all(),
        required=False,
        allow_null=True
    )
    
    # Read-only fields for response
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = SavedFilter
        fields = [
            'id',
            'name',
            'description',
            'in_digest',
            'stages',
            'round_statuses',
            'categories',
            'participants',
            'participant_filter_mode',
            'participant_filter_ids',
            'participant_filter_types',
            'search',
            'featured',
            'is_open',
            'new',
            'trending',
            'hide_liked',
            'start_date',
            'end_date',
            'min_signals',
            'max_signals',
            'is_default',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """
        Validate that the filter name is unique for the user
        """
        user = self.context.get('request').user
        filter_id = self.instance.id if self.instance else None
        
        # Check if a filter with this name already exists for this user
        existing = SavedFilter.objects.filter(user=user, name=value)
        if filter_id:
            existing = existing.exclude(id=filter_id)
        
        if existing.exists():
            raise serializers.ValidationError(
                f"You already have a saved filter named '{value}'"
            )
        
        return value
    
    def validate_is_default(self, value):
        """
        If setting as default, ensure other filters are unmarked
        """
        if value:
            user = self.context.get('request').user
            filter_id = self.instance.id if self.instance else None
            
            # This will be handled in the save method, but we validate here too
            existing_default = SavedFilter.objects.filter(user=user, is_default=True)
            if filter_id:
                existing_default = existing_default.exclude(id=filter_id)
            
            if existing_default.exists():
                # This is not an error, just informational
                # The save method will handle unsetting other defaults
                pass
        
        return value
    
    def create(self, validated_data):
        """
        Create a new saved filter for the authenticated user
        """
        user = self.context['request'].user
        
        # Extract many-to-many fields
        categories = validated_data.pop('categories', [])
        participants = validated_data.pop('participants', [])
        
        # Create the saved filter
        saved_filter = SavedFilter.objects.create(user=user, **validated_data)
        
        # Set many-to-many relationships
        if categories:
            saved_filter.categories.set(categories)
        if participants:
            saved_filter.participants.set(participants)
        
        return saved_filter
    
    def update(self, instance, validated_data):
        """
        Update an existing saved filter
        """
        # Extract many-to-many fields
        categories = validated_data.pop('categories', None)
        participants = validated_data.pop('participants', None)
        
        # Update scalar fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update many-to-many relationships if provided
        if categories is not None:
            instance.categories.set(categories)
        if participants is not None:
            instance.participants.set(participants)
        
        return instance
    
    def to_representation(self, instance):
        """
        Customize the output representation
        """
        representation = super().to_representation(instance)
        
        # Add category and participant details
        representation['categories'] = [
            {
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug
            }
            for cat in instance.categories.all()
        ]
        
        representation['participants'] = [
            {
                'id': part.id,
                'name': part.name,
                'slug': part.slug,
                'is_private': part.is_private
            }
            for part in instance.participants.all()
        ]
        
        return representation


class SavedFilterListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing saved filters
    Only includes essential fields for list views
    """
    categories_count = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    has_filters = serializers.SerializerMethodField()
    
    class Meta:
        model = SavedFilter
        fields = [
            'id',
            'name',
            'description',
            'is_default',
            'in_digest',
            'categories_count',
            'participants_count',
            'has_filters',
            'created_at',
            'updated_at',
        ]
    
    def get_categories_count(self, obj):
        """Return the count of associated categories"""
        return obj.categories.count()
    
    def get_participants_count(self, obj):
        """Return the count of associated participants"""
        return obj.participants.count()
    
    def get_has_filters(self, obj):
        """Check if this saved filter has any active filter criteria"""
        return any([
            obj.search,
            obj.stages,
            obj.round_statuses,
            obj.featured is not None,
            obj.is_open is not None,
            obj.new is not None,
            obj.trending is not None,
            obj.start_date,
            obj.end_date,
            obj.min_signals is not None,
            obj.max_signals is not None,
            obj.categories.exists(),
            obj.participants.exists(),
            obj.participant_filter_mode is not None,
            obj.participant_filter_ids,
            obj.participant_filter_types,
        ])


