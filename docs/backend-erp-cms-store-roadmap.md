# Backend ERP/CMS/Store Roadmap

## Objectif

Organiser le backend en trois surfaces fonctionnelles pour faciliter la maintenance aujourd'hui et une migration progressive vers des microservices demain.

## Surfaces

### Store

API publique consommee par le storefront.

- Catalogue public: produits, categories, packs visibles.
- Panier/checkout: devis commande, livraison, promo, fidelite.
- Compte client: profil, commandes, wishlist, avis.
- Contenu public: header, drop countdown, vlog, pages frontend.
- Tracking public analytics.

### CMS

Back-office contenu et experience frontend.

- Pages CMS frontend: About, FAQ, Contact, policies.
- Home sections, menus, SEO, medias.
- Header video/image, drop countdown, vlog.
- Engagement: avis, commentaires, moderation.
- Planification de contenu.

### ERP

Operations internes e-commerce.

- Dashboard executif.
- Commandes avancees, factures, bons de livraison.
- Inventaire, mouvements de stock, alertes.
- Clients/CRM, segments, notes internes.
- Marketing, campagnes, promos, notifications.
- Audit log, exports, analytics business.

## Regles Backend

- Les routers ne doivent contenir que:
  - validation FastAPI,
  - dependances auth/db,
  - appel au service,
  - mapping de reponse si necessaire.
- La logique metier doit vivre dans `app/services`:
  - `app/services/services_erp` pour operations internes,
  - `app/services/services_cms` pour contenu/admin CMS,
  - `app/services/services_store` pour storefront/public.
- Les routers sont organises par surface dans `app/routers`:
  - `app/routers/routers_erp`,
  - `app/routers/routers_cms`,
  - `app/routers/routers_store`.
- Aucun fichier router ne doit rester directement dans `app/routers`.
- Aucun fichier service ne doit rester directement dans `app/services`.
- Les routers `routers_store` ne doivent jamais importer `require_permission`, `get_current_admin` ou `require_superadmin`.
- Quand une URL contient a la fois une lecture publique et une mutation admin, on garde le meme prefixe HTTP mais on separe les fichiers:
  - lecture publique dans `routers_store`,
  - mutation/admin dans `routers_erp` ou `routers_cms`.
- Les routes publiques restent sous les prefixes metier existants (`/products`, `/orders`, `/storefront/...`).
- Les surfaces admin doivent converger vers des prefixes clairs:
  - `/admin/cms/...` pour contenu et experience.
  - `/admin/erp/...` pour operations internes.
  - `/admin/...` reste compatible pendant la migration.
- Les outils transverses restent dans `app/core` ou dans un service de surface:
  - pagination,
  - notifications,
  - audit,
  - permissions,
  - exports.
- Les nouvelles listes doivent proposer une reponse paginee standard:
  - `items`,
  - `total`,
  - `page`,
  - `page_size`,
  - `pages`,
  - `has_next`,
  - `has_prev`,
  - `sort`,
  - `filters`.

## Prochaine Decoupe Technique

1. Ajouter `audit_log` transversal.
2. Ajouter `inventory` ERP: mouvements, alertes stock faible, export CSV.
3. Renforcer `orders` ERP: timeline, notes internes, tags, assignation admin.
4. Ajouter `crm` ERP: segments clients, notes, historique enrichi.
5. Ajouter `cms_content`: pages frontend, SEO, menus, blocs homepage.
6. Migrer les routes admin existantes vers des aliases `/admin/erp/*` et `/admin/cms/*`.
