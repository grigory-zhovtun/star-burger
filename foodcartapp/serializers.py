from django.db import transaction
from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=OrderItem.product.field.related_model.objects.all())

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True, allow_empty=False, write_only=True)
    phonenumber = PhoneNumberField()

    class Meta:
        model = Order
        fields = ['products', 'firstname', 'lastname', 'phonenumber', 'address']

    @transaction.atomic
    def create(self, validated_data):
        products_data = validated_data.pop('products')
        order = Order.objects.create(**validated_data)
        for item_data in products_data:
            OrderItem.objects.create(
                order=order,
                price=item_data['product'].price,
                **item_data
            )
        return order
