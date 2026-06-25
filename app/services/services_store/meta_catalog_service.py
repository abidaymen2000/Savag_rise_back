import csv
import io
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

from fastapi import Response

from app.config import settings
from app.domain.inventory import stock_available_value
from app.crud import product as product_crud
from app.services.services_store.meta_ids import meta_item_group_id, meta_safe_id, meta_variant_content_id


META_CATALOG_FIELDS = [
    "id",
    "title",
    "description",
    "availability",
    "condition",
    "price",
    "link",
    "image_link",
    "brand",
    "item_group_id",
    "color",
    "size",
    "gender",
    "age_group",
    "product_type",
    "google_product_category",
    "additional_image_link",
]


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return re.sub(r"\s+", " ", str(value)).strip() or fallback


def first_url(images: Iterable[Any]) -> Optional[str]:
    for image in images or []:
        url = image.get("url") if isinstance(image, dict) else image
        if url:
            return str(url)
    return None


def additional_urls(images: Iterable[Any], primary_url: Optional[str]) -> str:
    urls: List[str] = []
    for image in images or []:
        url = image.get("url") if isinstance(image, dict) else image
        if url and str(url) != primary_url:
            urls.append(str(url))
    return ",".join(urls[:10])


def normalize_gender(value: Optional[str]) -> str:
    gender = (value or "unisex").strip().lower()
    if gender in {"man", "men", "male", "homme", "hommes"}:
        return "male"
    if gender in {"woman", "women", "female", "femme", "femmes"}:
        return "female"
    return "unisex"


def format_price(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:.2f} {settings.META_CATALOG_CURRENCY}"


def product_link(product_id: str, color: Optional[str] = None, size: Optional[str] = None) -> str:
    path = settings.META_PRODUCT_PATH_TEMPLATE.format(id=product_id)
    base = f"{str(settings.FRONTEND_URL).rstrip('/')}/{path.lstrip('/')}"
    params = {key: value for key, value in {"color": color, "size": size}.items() if value}
    return f"{base}?{urlencode(params)}" if params else base


def product_type(product: Dict[str, Any]) -> str:
    categories = product.get("categories") or []
    if categories:
        return " > ".join(str(category) for category in categories)
    return clean_text(product.get("style"), "Clothing")


def base_row(product: Dict[str, Any], product_id: str, images: Iterable[Any]) -> Dict[str, str]:
    title = clean_text(product.get("full_name") or product.get("name"), "Savage Rise product")
    description = clean_text(product.get("description"), title)
    primary_image = first_url(images)
    return {
        "title": title,
        "description": description,
        "condition": "new",
        "price": format_price(product.get("price")),
        "brand": settings.META_CATALOG_BRAND,
        "item_group_id": meta_item_group_id(product_id, product.get("style_id")),
        "gender": normalize_gender(product.get("gender")),
        "age_group": "adult",
        "product_type": product_type(product),
        "google_product_category": "Apparel & Accessories > Clothing",
        "image_link": primary_image or "",
        "additional_image_link": additional_urls(images, primary_image),
    }


def variant_rows(product: Dict[str, Any], product_id: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    product_in_stock = bool(product.get("in_stock", True))

    for variant in product.get("variants") or []:
        color = clean_text(variant.get("color"))
        sizes = variant.get("sizes") or []
        images = variant.get("images") or []
        base = base_row(product, product_id, images)

        if not sizes:
            rows.append({
                **base,
                "id": meta_variant_content_id(product_id, color=color),
                "color": color,
                "size": "",
                "availability": "in stock" if product_in_stock else "out of stock",
                "link": product_link(product_id, color=color),
            })
            continue

        for size_stock in sizes:
            size = clean_text(size_stock.get("size"))
            stock = stock_available_value(size_stock)
            rows.append({
                **base,
                "id": meta_variant_content_id(product_id, color=color, size=size),
                "color": color,
                "size": size,
                "availability": "in stock" if product_in_stock and stock > 0 else "out of stock",
                "link": product_link(product_id, color=color, size=size),
            })

    return rows


def product_row(product: Dict[str, Any], product_id: str) -> Dict[str, str]:
    images = []
    for variant in product.get("variants") or []:
        images.extend(variant.get("images") or [])
    base = base_row(product, product_id, images)
    return {
        **base,
        "id": meta_safe_id(product.get("sku") or product_id),
        "color": "",
        "size": "",
        "availability": "in stock" if product.get("in_stock", True) else "out of stock",
        "link": product_link(product_id),
    }


def rows_for_product(product: Dict[str, Any]) -> List[Dict[str, str]]:
    product_id = str(product["_id"])
    rows = variant_rows(product, product_id)
    return rows or [product_row(product, product_id)]


async def build_meta_catalog_csv(db, include_out_of_stock: bool, include_missing_images: bool) -> Response:
    products = await product_crud.list_products_for_meta_catalog(db, limit=5000)
    rows: List[Dict[str, str]] = []
    for product in products:
        for row in rows_for_product(product):
            if not include_out_of_stock and row["availability"] != "in stock":
                continue
            if not include_missing_images and not row["image_link"]:
                continue
            rows.append({field: row.get(field, "") for field in META_CATALOG_FIELDS})

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=META_CATALOG_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="savage-rise-meta-catalog.csv"',
            "Cache-Control": "public, max-age=900",
        },
    )
