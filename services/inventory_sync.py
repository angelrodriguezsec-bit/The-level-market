def sync_inventory(suppliers, stores, skus, buffer=2):
    suppliers = suppliers.values() if isinstance(suppliers, dict) else suppliers
    stores = stores.values() if isinstance(stores, dict) else stores
    synced = {}
    for sku in skus:
        total_stock = sum(
            offer.stock
            for supplier in suppliers
            for offer in supplier.get_offers(sku)
        )
        quantity = max(0, total_stock - buffer)
        for store in stores:
            store.update_inventory(sku, quantity)
        synced[sku] = quantity
    return synced