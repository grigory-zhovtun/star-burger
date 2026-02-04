import requests
from geopy import distance

from django import forms
from django.shortcuts import redirect, render
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import user_passes_test

from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views


from foodcartapp.models import Product, Restaurant, Order
from places.models import Place
from places.coordinates import fetch_coordinates


class Login(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Укажите имя пользователя'
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )


class LoginView(View):
    def get(self, request, *args, **kwargs):
        form = Login()
        return render(request, "login.html", context={
            'form': form
        })

    def post(self, request):
        form = Login(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect("restaurateur:RestaurantView")
                return redirect("start_page")

        return render(request, "login.html", context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_products(request):
    restaurants = list(Restaurant.objects.order_by('name'))
    products = list(Product.objects.prefetch_related('menu_items'))

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name="products_list.html", context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_restaurants(request):
    return render(request, template_name="restaurants_list.html", context={
        'restaurants': Restaurant.objects.all(),
    })


def get_coordinates_safe(address):
    try:
        return fetch_coordinates(address)
    except requests.exceptions.RequestException:
        return None


@user_passes_test(is_manager, login_url='restaurateur:login')
def view_orders(request):
    orders = list(Order.objects.exclude(
        status=Order.STATUS_COMPLETED
    ).with_total_price().with_available_restaurants())

    addresses = set()
    for order in orders:
        addresses.add(order.address)
        for restaurant in order.available_restaurants:
            addresses.add(restaurant.address)

    places = Place.objects.filter(address__in=addresses)
    coordinates_by_address = {
        place.address: (place.lat, place.lon)
        for place in places
        if place.lat is not None and place.lon is not None
    }

    order_items = []
    for order in orders:
        if order.restaurant:
            available_restaurants = None
        else:
            available_restaurants = order.available_restaurants
            if available_restaurants:
                order_coords = coordinates_by_address.get(order.address)
                if not order_coords:
                    order_coords = get_coordinates_safe(order.address)
                    if order_coords:
                        coordinates_by_address[order.address] = order_coords

                if order_coords:
                    restaurants_with_distance = []
                    for restaurant in available_restaurants:
                        restaurant_coords = coordinates_by_address.get(restaurant.address)
                        if not restaurant_coords:
                            restaurant_coords = get_coordinates_safe(restaurant.address)
                            if restaurant_coords:
                                coordinates_by_address[restaurant.address] = restaurant_coords

                        if restaurant_coords:
                            dist = distance.distance(order_coords, restaurant_coords).km
                            restaurants_with_distance.append({
                                'restaurant': restaurant,
                                'distance': round(dist, 3),
                            })
                        else:
                            restaurants_with_distance.append({
                                'restaurant': restaurant,
                                'distance': None,
                            })
                    available_restaurants = sorted(
                        restaurants_with_distance,
                        key=lambda x: x['distance'] if x['distance'] is not None else float('inf')
                    )
                else:
                    available_restaurants = None

        order_items.append({
            'order': order,
            'available_restaurants': available_restaurants,
        })

    return render(request, template_name='order_items.html', context={
        'order_items': order_items,
    })
