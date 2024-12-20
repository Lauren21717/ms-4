from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.functions import Lower

from .models import Product, Category, ShopByOption
from .forms import ProductForm
from profiles.models import UserProfile
from reviews.models import ProductReview


def collection(request):
    """
    A view to show all products, including sorting and search queries
    """
    products = Product.objects.all()
    query = None
    categories = None
    shop_by_options = None
    sort = None
    direction = None
    page_header = "All Collections"
    page_description = "Browse our full range of products across various \
        categories, from essentials to exclusive items, \
        crafted to meet your every need."

    if request.GET:
        # Sorting
        if 'sort' in request.GET:
            sortkey = request.GET['sort']
            sort = sortkey

            # Handling sorting by different fields
            if sortkey == 'name':
                sortkey = 'lower_name'
                products = products.annotate(lower_name=Lower('name'))
            elif sortkey == 'category':
                sortkey = 'category__name'
            elif sortkey == 'shop_by_option':
                sortkey = 'shop_by__name'

            if 'direction' in request.GET:
                direction = request.GET['direction']
                if direction == 'desc':
                    sortkey = f'-{sortkey}'

            products = products.order_by(sortkey)

        # Category Filtering
        if 'category' in request.GET:
            category_names = request.GET['category'].split(',')
            products = products.filter(category__name__in=category_names)
            categories = Category.objects.filter(name__in=category_names)
            if len(category_names) == 1:
                category = Category.objects.get(name=category_names[0])
                page_header = category.header
                page_description = category.description

        # Shop By Options Filtering
        if 'shop_by_option' in request.GET:
            shop_by_option_names = request.GET['shop_by_option'].split(',')  # noqa
            products = products.filter(
                shop_by__name__in=shop_by_option_names
            )
            shop_by_options = ShopByOption.objects.filter(
                name__in=shop_by_option_names
            )
            if len(shop_by_option_names) == 1:
                shop_by_option = ShopByOption.objects.get(
                    name=shop_by_option_names[0]
                )
                category = shop_by_option.category
                page_header = f"{shop_by_option.friendly_name}"
                page_description = category.description

        # Clearance (Special Offer) Filtering
        if 'offer' in request.GET:
            page_header = "Special Offers"
            page_description = "Grab limited-time discounts on selected items."  # noqa
            products = products.filter(is_special_offer=True)

        # New Arrivals (Featured Products) Filtering
        if 'new_arrivals' in request.GET:
            page_header = "New Arrivals"
            page_description = "Discover our latest additions to the collection."  # noqa
            products = products.filter(is_featured=True)

        # All Specials (Both Special Offer and Featured Products)
        if 'all_specials' in request.GET:
            products = products.filter(Q(is_special_offer=True) | Q(is_featured=True))  # noqa
            page_header = "Exclusive Specials"
            page_description = "Discover exclusive deals and the latest additions in one place. Shop now for limited-time discounts and fresh new products!"   # noqa

        # Search Query
        if 'q' in request.GET:
            query = request.GET['q']
            if not query:
                messages.error(
                    request,
                    "You didn't enter any search criteria!"
                )
                return redirect(reverse('collection'))

            queries = Q(name__icontains=query) | Q(description__icontains=query)  # noqa
            products = products.filter(queries)

    current_sorting = f'{sort}_{direction}'

    context = {
        'products': products,
        'search_term': query,
        'current_categories': categories,
        'current_shop_by_options': shop_by_options,
        'current_sorting': current_sorting,
        'page_header': page_header,
        'page_description': page_description,
    }

    return render(request, 'collection/collection.html', context)


def product_detail(request, product_id):
    """
    A view to show individual product details
    """

    product = get_object_or_404(Product, pk=product_id)
    reviews = ProductReview.objects.filter(product=product).order_by('-created_at')  # noqa
    total_reviews = reviews.count()
    profile = False
    already_review = True
    validated_purchase = False

    # Check if the user is authenticated and get the user profile
    if request.user.is_authenticated:
        profile = UserProfile.objects.get(user=request.user)

        # Check if the user has already reviewed the product
        already_review = ProductReview.objects.filter(
            product=product, user_profile=profile
        ).exists()

        # Check if the user has purchased the product
        if product in profile.user_purchases.all():
            validated_purchase = True

    context = {
        'product': product,
        'reviews': reviews,
        'average_rating': product.rating,
        'total_reviews': total_reviews,
        'profile': profile,
        'validated_purchase': validated_purchase,
        'already_reviewed': already_review,
    }

    return render(request, 'collection/product_detail.html', context)


@login_required
def add_product(request):
    """
    Add a product to the store
    """
    if not request.user.is_superuser:
        messages.error(request, 'Sorry, only store owners can do that.')
        return redirect(reverse('home'))

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(
                request,
                'Successfully added product!'
            )
            return redirect(reverse('product_detail', args=[product.id]))
        else:
            messages.error(
                request,
                'Failed to add product. Please ensure the form is valid.'
            )
    else:
        form = ProductForm()
    template = 'collection/add_product.html'
    context = {
        'form': form,
    }

    return render(request, template, context)


@login_required
def edit_product(request, product_id):
    """
    Edit a product in the store
    """
    if not request.user.is_superuser:
        messages.error(request, 'Sorry, only store owners can do that.')
        return redirect(reverse('home'))

    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Successfully updated product!')
            return redirect(reverse('product_detail', args=[product.id]))
        else:
            messages.error(
                request,
                'Failed to update product. Please ensure the form is valid.'
            )
    else:
        form = ProductForm(instance=product)
        messages.info(request, f'You are editing {product.name}')

    template = 'collection/edit_product.html'
    context = {
        'form': form,
        'product': product,
    }

    return render(request, template, context)


@login_required
def delete_product(request, product_id):
    """
    Delete a product from the store
    """
    if not request.user.is_superuser:
        messages.error(request, 'Sorry, only store owners can do that.')
        return redirect(reverse('home'))

    product = get_object_or_404(Product, pk=product_id)
    product.delete()
    messages.success(request, 'Product deleted!')
    return redirect(reverse('collection'))
