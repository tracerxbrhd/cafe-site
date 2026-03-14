from .cart import cart_count, cart_lines


def cart_info(request):
    _, total = cart_lines(request.session)
    return {
        "cart_count": cart_count(request.session),
        "cart_total": total,
    }
