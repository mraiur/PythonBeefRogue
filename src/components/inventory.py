import tcod

from src.game_messages import Message

"""
    Handles player inventory
    Capacity - number of items player can carry
    Items - items in the inventory
"""


class Inventory:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = []

    # Adds item to the player's inventory if not full
    def add_item(self, item):
        results = []

        if len(self.items) >= self.capacity:
            results.append({
                'item_added': None,
                'message': Message('You cannot carry any more, your inventory is full', tcod.yellow)
            })
        else:
            results.append({
                'item_added': item,
                'message': Message('You pick up the {0} and place it in your inventory'.format(item.name),
                                   tcod.blue)
            })

            self.items.append(item)

        return results

    # Uses an item from inventory
    def use(self, item_entity, **kwargs):
        results = []

        item_component = item_entity.item

        if item_component.use_function is None:
            results.append({'message': Message('The {0} cannot be used.'.format(item_entity.name), tcod.yellow)})
        else:
            # Determines if targeting is true or not and if the coords were passed
            if item_component.targeting and not (kwargs.get('target_x') or kwargs.get('target_y')):
                results.append({'targeting': item_entity})
            else:
                kwargs = {**item_component.function_kwargs, **kwargs}
                item_use_results = item_component.use_function(self.owner, **kwargs)

                for item_use_result in item_use_results:
                    if item_use_result.get('consumed'):
                        self.remove_item(item_entity)

                results.extend(item_use_results)

        return results

    # Remove item from inventory
    def remove_item(self, item):
        self.items.remove(item)

    # Drops item at player's coordinates
    def drop_item(self, item):
        results = []

        item.x = self.owner.x
        item.y = self.owner.y

        self.remove_item(item)
        results.append({'item_dropped': item, 'message': Message('You dropped the {0}.'.format(item.name),
                                                                 tcod.yellow)})

        return results
