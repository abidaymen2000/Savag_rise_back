from typing import Any, Dict, List


EVENT_CATALOG: Dict[str, Dict[str, Any]] = {
    # Navigation
    "page_viewed": {
        "category": "navigation",
        "label": "Page vue",
        "description": "Une page du store a ete affichee.",
        "recommended_metadata": ["page_path", "page_title", "url"],
    },
    "collection_viewed": {
        "category": "navigation",
        "label": "Collection vue",
        "description": "Une collection, categorie ou listing a ete affiche.",
        "recommended_metadata": ["collection_id", "collection_name", "page_path"],
    },
    "search_submitted": {
        "category": "navigation",
        "label": "Recherche",
        "description": "Un utilisateur a lance une recherche.",
        "recommended_metadata": ["query", "filters", "results_count", "page_path"],
    },
    "filter_applied": {
        "category": "navigation",
        "label": "Filtre applique",
        "description": "Un filtre catalogue a ete applique.",
        "recommended_metadata": ["filter_name", "filter_value", "page_path"],
    },
    "sort_changed": {
        "category": "navigation",
        "label": "Tri change",
        "description": "Le tri du catalogue a ete modifie.",
        "recommended_metadata": ["sort", "page_path"],
    },

    # Product engagement
    "product_viewed": {
        "category": "product",
        "label": "Produit vu",
        "description": "Une fiche produit a ete consultee.",
        "recommended_metadata": ["product_name", "style_id", "page_path"],
    },
    "product_image_viewed": {
        "category": "product",
        "label": "Image produit vue",
        "description": "Une image ou slide produit a ete affichee.",
        "recommended_metadata": ["product_id", "image_index", "variant_id"],
    },
    "size_selected": {
        "category": "product",
        "label": "Taille selectionnee",
        "description": "Une taille produit a ete selectionnee.",
        "recommended_metadata": ["product_id", "size", "page_path"],
    },
    "color_selected": {
        "category": "product",
        "label": "Couleur selectionnee",
        "description": "Une couleur produit a ete selectionnee.",
        "recommended_metadata": ["product_id", "color", "page_path"],
    },
    "variant_selected": {
        "category": "product",
        "label": "Variante selectionnee",
        "description": "Une variante produit complete a ete selectionnee.",
        "recommended_metadata": ["product_id", "variant_id", "color", "size"],
    },
    "size_guide_opened": {
        "category": "product",
        "label": "Guide des tailles ouvert",
        "description": "Le guide des tailles a ete ouvert.",
        "recommended_metadata": ["product_id", "page_path"],
    },

    # Cart and checkout
    "add_to_cart": {
        "category": "cart",
        "label": "Ajout panier",
        "description": "Un article a ete ajoute au panier.",
        "recommended_metadata": ["product_id", "product_name", "qty", "size", "color", "unit_price"],
    },
    "remove_from_cart": {
        "category": "cart",
        "label": "Retrait panier",
        "description": "Un article a ete retire du panier.",
        "recommended_metadata": ["product_id", "qty", "page_path"],
    },
    "cart_viewed": {
        "category": "cart",
        "label": "Panier vu",
        "description": "Le panier a ete affiche.",
        "recommended_metadata": ["items_count", "cart_total", "page_path"],
    },
    "cart_updated": {
        "category": "cart",
        "label": "Panier modifie",
        "description": "La quantite ou une variante du panier a ete modifiee.",
        "recommended_metadata": ["product_id", "qty", "cart_total"],
    },
    "checkout_started": {
        "category": "checkout",
        "label": "Checkout commence",
        "description": "Le client est entre dans le tunnel de commande.",
        "recommended_metadata": ["items_count", "cart_total", "payment_method"],
    },
    "shipping_info_submitted": {
        "category": "checkout",
        "label": "Livraison renseignee",
        "description": "Les informations de livraison ont ete soumises.",
        "recommended_metadata": ["country", "city", "shipping_rate_id", "shipping_amount"],
    },
    "payment_started": {
        "category": "checkout",
        "label": "Paiement commence",
        "description": "Le paiement a ete initie.",
        "recommended_metadata": ["payment_method", "total_amount"],
    },
    "payment_success": {
        "category": "checkout",
        "label": "Paiement reussi",
        "description": "Un paiement a ete valide.",
        "recommended_metadata": ["payment_method", "total_amount", "loyalty_points_earned"],
    },
    "payment_failed": {
        "category": "checkout",
        "label": "Paiement echoue",
        "description": "Une tentative de paiement a echoue.",
        "recommended_metadata": ["payment_method", "reason", "total_amount"],
    },
    "order_completed": {
        "category": "checkout",
        "label": "Commande creee",
        "description": "Une commande a ete creee.",
        "recommended_metadata": ["total_amount", "payment_method", "items", "promo_code"],
    },
    "order_cancelled": {
        "category": "checkout",
        "label": "Commande annulee",
        "description": "Une commande a ete annulee.",
        "recommended_metadata": ["order_id", "reason", "total_amount"],
    },
    "coupon_applied": {
        "category": "checkout",
        "label": "Code promo applique",
        "description": "Un code promo a ete applique a une commande.",
        "recommended_metadata": ["coupon_code", "discount_value", "order_total"],
    },
    "coupon_failed": {
        "category": "checkout",
        "label": "Code promo refuse",
        "description": "Un code promo a ete refuse.",
        "recommended_metadata": ["coupon_code", "reason", "order_total"],
    },

    # Account and loyalty
    "account_created": {
        "category": "account",
        "label": "Compte cree",
        "description": "Un compte client a ete cree.",
        "recommended_metadata": ["email_domain"],
    },
    "email_verified": {
        "category": "account",
        "label": "Email verifie",
        "description": "Un email client a ete verifie.",
        "recommended_metadata": [],
    },
    "login": {
        "category": "account",
        "label": "Connexion",
        "description": "Un client s'est connecte.",
        "recommended_metadata": ["email_domain"],
    },
    "logout": {
        "category": "account",
        "label": "Deconnexion",
        "description": "Un client s'est deconnecte.",
        "recommended_metadata": [],
    },
    "wishlist_added": {
        "category": "account",
        "label": "Ajout wishlist",
        "description": "Un produit a ete ajoute a la wishlist.",
        "recommended_metadata": ["product_id", "product_name"],
    },
    "wishlist_removed": {
        "category": "account",
        "label": "Retrait wishlist",
        "description": "Un produit a ete retire de la wishlist.",
        "recommended_metadata": ["product_id"],
    },
    "loyalty_points_redeemed": {
        "category": "account",
        "label": "Points fidelite utilises",
        "description": "Des points fidelite ont ete utilises.",
        "recommended_metadata": ["points", "discount_value", "order_id"],
    },

    # Content and campaigns
    "notify_me_clicked": {
        "category": "content",
        "label": "Notify me",
        "description": "Le bouton de notification drop a ete clique.",
        "recommended_metadata": ["drop_key", "drop_name", "page_path"],
    },
    "drop_subscription_created": {
        "category": "content",
        "label": "Inscription drop",
        "description": "Un utilisateur s'est inscrit a une notification drop.",
        "recommended_metadata": ["drop_key", "drop_name"],
    },
    "vlog_episode_viewed": {
        "category": "content",
        "label": "Episode vlog vu",
        "description": "Un episode vlog a ete visionne.",
        "recommended_metadata": ["episode_id", "chapter_id", "title"],
    },
    "review_created": {
        "category": "content",
        "label": "Avis cree",
        "description": "Un avis produit a ete cree.",
        "recommended_metadata": ["product_id", "rating"],
    },
    "contact_submitted": {
        "category": "content",
        "label": "Contact envoye",
        "description": "Le formulaire contact a ete envoye.",
        "recommended_metadata": ["subject"],
    },

    # Generic UI
    "button_clicked": {
        "category": "ui",
        "label": "Bouton clique",
        "description": "Un bouton ou CTA a ete clique.",
        "recommended_metadata": ["button_id", "label", "page_path"],
    },
    "link_clicked": {
        "category": "ui",
        "label": "Lien clique",
        "description": "Un lien a ete clique.",
        "recommended_metadata": ["link_id", "label", "href", "page_path"],
    },
    "form_started": {
        "category": "ui",
        "label": "Formulaire commence",
        "description": "Un formulaire a ete commence.",
        "recommended_metadata": ["form_id", "page_path"],
    },
    "form_submitted": {
        "category": "ui",
        "label": "Formulaire soumis",
        "description": "Un formulaire a ete soumis.",
        "recommended_metadata": ["form_id", "page_path"],
    },
    "form_error": {
        "category": "ui",
        "label": "Erreur formulaire",
        "description": "Une erreur de formulaire a ete affichee.",
        "recommended_metadata": ["form_id", "field", "error_code", "page_path"],
    },
}


ALLOWED_ANALYTICS_EVENTS = set(EVENT_CATALOG.keys())


def get_event_definition(event_name: str) -> Dict[str, Any]:
    definition = EVENT_CATALOG[event_name]
    return {"event_name": event_name, **definition}


def event_catalog() -> List[Dict[str, Any]]:
    return [get_event_definition(name) for name in sorted(EVENT_CATALOG)]

