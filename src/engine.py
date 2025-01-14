import tcod

from src.components.menus import main_menu, message_box
from src.death_functions import kill_monster, kill_player
from src.entity import get_blocking_entities_at_location
from src.fov_functions import initialize_fov, recompute_fov
from src.game_messages import Message
from src.game_states import GameStates
from src.input_handlers import handle_keys, handle_main_menu, handle_mouse
from src.loader_functions.data_loaders import load_game, save_game
from src.loader_functions.initialize_new_game import get_game_constants, get_game_variables
from src.render_functions import clear_all, render_all

# TODO add message of what is at player's feet

"""
       Main file where game parameters and game loop resides
"""


# Logic of main game
def play_game(player, entities, game_map, message_log, game_state, con, panel, constants):
    # Field of view variables
    fov_recompute = True                    # We only need to recompute when character moves
    fov_map = initialize_fov(game_map)

    # Variables for keyboard and mouse inputs
    key = tcod.Key()
    mouse = tcod.Mouse()

    # Player goes first
    game_state = GameStates.PLAYERS_TURN

    # Save previous game state (for inventory support)
    previous_game_state = game_state

    # Saves targeting item
    targeting_item = None

    # Main game loop
    while not tcod.console_is_window_closed():
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)

        # Updates field of view if needed
        if fov_recompute:
            recompute_fov(fov_map, player.x, player.y, constants['fov_radius'], constants['fov_light_walls'],
                          constants['fov_algorithm'])

        # Draws player and sets recompute to false until next player move
        render_all(con, panel, entities, player, game_map, fov_map, fov_recompute, message_log,
                   constants['screen_width'], constants['screen_height'], constants['bar_width'],
                   constants['panel_height'], constants['panel_y'], mouse, constants['colors'], game_state)
        fov_recompute = False
        tcod.console_flush()

        # Updates spot last at with a blank (avoids multiple @'s)
        clear_all(con, entities)

        # Keyboard and mouse inputs
        action = handle_keys(key, game_state)
        mouse_action = handle_mouse(mouse)

        # TODO add in help menu that lists commands, available both through menu and by hitting '?'
        # Action handlers
        move = action.get('move')
        wait = action.get('wait')
        pickup = action.get('pickup')
        show_inventory = action.get('show_inventory')
        drop_inventory = action.get('drop_inventory')
        inventory_index = action.get('inventory_index')
        level_up = action.get('level_up')
        show_character_screen = action.get('show_character_screen')
        # TODO add in take_stairs_up
        take_stairs_down = action.get('take_stairs_down')
        exit = action.get('exit')
        fullscreen = action.get('fullscreen')

        # Mouse action handlers
        left_click = mouse_action.get('left_click')
        right_click = mouse_action.get('right_click')

        # List to hold for result of battles
        player_turn_results = []

        # Player turn and handling of item pickups
        if move and game_state == GameStates.PLAYERS_TURN:
            dx, dy = move
            destination_x = player.x + dx
            destination_y = player.y + dy

            if not game_map.is_blocked(destination_x, destination_y):
                target = get_blocking_entities_at_location(entities, destination_x, destination_y)

                if target:
                    attack_results = player.fighter.attack(target)
                    player_turn_results.extend(attack_results)
                else:
                    player.move(dx, dy)
                    fov_recompute = True

                game_state = GameStates.ENEMY_TURN

        # Player waits for a turn (and does nothing)
        elif wait and game_state == GameStates.PLAYERS_TURN:
            message_log.add_message(Message('You twiddle your thumbs for a turn.', tcod.turquoise))
            game_state = GameStates.ENEMY_TURN

        # Pickup items
        elif pickup and game_state == GameStates.PLAYERS_TURN:
            for entity in entities:
                if entity.item and entity.x == player.x and entity.y == player.y:
                    pickup_results = player.inventory.add_item(entity)
                    player_turn_results.extend(pickup_results)

                    break
            else:
                message_log.add_message(Message('There is nothing here to pick up.', tcod.yellow))

        # Show inventory
        if show_inventory:
            previous_game_state = game_state
            game_state = GameStates.SHOW_INVENTORY

        # Drops item from inventory
        if drop_inventory:
            previous_game_state = game_state
            game_state = GameStates.DROP_INVENTORY

        # Use or drop item (only when in inventory game state and not dead)
        if inventory_index is not None and previous_game_state != GameStates.PLAYER_DEAD and inventory_index < len(
                player.inventory.items):
            item = player.inventory.items[inventory_index]

            if game_state == GameStates.SHOW_INVENTORY:
                player_turn_results.extend(player.inventory.use(item, entities=entities, fov_map=fov_map))
            elif game_state == GameStates.DROP_INVENTORY:
                player_turn_results.extend(player.inventory.drop_item(item))

        # Leveling up
        if level_up:
            if level_up == 'hp':
                player.fighter.max_hp += 20
                player.fighter.hp += 20
            elif level_up == 'str':
                player.fighter.power += 1
            elif level_up == 'def':
                player.fighter.defense += 1

            game_state = previous_game_state

        # Character screen, switches to appropriate game state
        if show_character_screen:
            previous_game_state = game_state
            game_state = GameStates.CHARACTER_SCREEN

        # TODO will likely need to add a stairs_down and stairs_up to entities when making going up floors
        # Goes down a flight of stairs, going to a new map
        if take_stairs_down and game_state == GameStates.PLAYERS_TURN:
            for entity in entities:
                if entity.stairs and entity.x == player.x and entity.y == player.y:
                    entities = game_map.next_floor(player, message_log, constants)
                    fov_map = initialize_fov(game_map)
                    fov_recompute = True
                    tcod.console_clear(con)

                    break
            else:
                message_log.add_message(Message('There are no stairs here.', tcod.yellow))

        # Targeting mode is active - left mouse click sets target, right mouse click cancels
        if game_state == GameStates.TARGETING:
            if left_click:
                target_x, target_y = left_click

                item_use_results = player.inventory.use(targeting_item, entities=entities, fov_map=fov_map,
                                                        target_x=target_x, target_y=target_y)
                player_turn_results.extend(item_use_results)
            elif right_click:
                player_turn_results.append({'targeting_cancelled': True})

        # Reverts back to previous game state while viewing inventory; otherwise, closes and saves game
        if exit:
            if game_state in (GameStates.SHOW_INVENTORY, GameStates.DROP_INVENTORY, GameStates.CHARACTER_SCREEN):
                game_state = previous_game_state
            elif game_state == GameStates.TARGETING:
                player_turn_results.append({'targeting_cancelled': True})
            else:
                save_game(player, entities, game_map, message_log, game_state)

                return True

        # Toggles fullscreen
        if fullscreen:
            tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

        # Iterates results after turn
        for player_turn_result in player_turn_results:
            message = player_turn_result.get('message')
            dead_entity = player_turn_result.get('dead')
            item_added = player_turn_result.get('item_added')
            item_consumed = player_turn_result.get('consumed')
            item_dropped = player_turn_result.get('item_dropped')
            targeting = player_turn_result.get('targeting')
            targeting_cancelled = player_turn_result.get('targeting_cancelled')
            xp = player_turn_result.get('xp')

            # Displays supplied message
            if message:
                message_log.add_message(message)

            # Player or monster has died
            if dead_entity:
                if dead_entity == player:
                    message, game_state = kill_player(dead_entity)
                else:
                    message = kill_monster(dead_entity)

                message_log.add_message(message)

            # Item was added to inventory
            if item_added:
                entities.remove(item_added)

                game_state = GameStates.ENEMY_TURN

            # Item was used
            if item_consumed:
                game_state = GameStates.ENEMY_TURN

            # Item was dropped
            if item_dropped:
                entities.append(item_dropped)

                game_state = GameStates.ENEMY_TURN

            # Targeting is activated, switch to targeting mode
            if targeting:
                previous_game_state = GameStates.PLAYERS_TURN
                game_state = GameStates.TARGETING

                targeting_item = targeting

                message_log.add_message(targeting_item.item.targeting_message)

            # Targeting was cancelled, revert to previous game state
            if targeting_cancelled:
                game_state = previous_game_state

                message_log.add_message(Message('Targeting cancelled.'))

            # Experience results
            if xp:
                leveled_up = player.level.add_xp(xp)
                message_log.add_message(Message('You gain {0} experience points.'.format(xp)))

                if leveled_up:
                    message_log.add_message(Message('You have leveled up and reached level {0}!'.format(
                        player.level.current_level), tcod.green))
                    previous_game_state = game_state
                    game_state = GameStates.LEVEL_UP

        # Enemies turn
        if game_state == GameStates.ENEMY_TURN:
            for entity in entities:
                if entity.ai:
                    enemy_turn_results = entity.ai.take_turn(player, fov_map, game_map, entities)

                    for enemy_turn_result in enemy_turn_results:
                        message = enemy_turn_result.get('message')
                        dead_entity = enemy_turn_result.get('dead')

                        if message:
                            message_log.add_message(message)

                        if dead_entity:
                            if dead_entity == player:
                                message, game_state = kill_player(dead_entity)
                            else:
                                message = kill_monster(dead_entity)

                            message_log.add_message(message)

                            if game_state == GameStates.PLAYER_DEAD:
                                break

                    if game_state == GameStates.PLAYER_DEAD:
                        break
            else:
                game_state = GameStates.PLAYERS_TURN


def main():
    # Grabs all the various game constants
    constants = get_game_constants()

    # Sets font
    tcod.console_set_custom_font('arial12x12.png', tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD)

    # Sets window parameters
    tcod.console_init_root(constants['screen_width'], constants['screen_height'], constants['game_title'],
                           False, tcod.RENDERER_OPENGL2, vsync=True)
    con = tcod.console_new(constants['screen_width'], constants['screen_height'])
    panel = tcod.console_new(constants['screen_width'], constants['panel_height'])

    # Sets saved game parameters to none
    player = None
    entities = []
    game_map = None
    message_log = None
    game_state = None

    # Menu and Load triggers
    show_main_menu = True
    show_load_error_message = False

    # Load main menu background
    main_menu_background_image = tcod.image_load('menu_background.png')

    # Inputs
    key = tcod.Key()
    mouse = tcod.Mouse()

    #
    # MAIN GAME LOOP
    #
    while not tcod.console_is_window_closed():
        # Check for events
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)

        # Main menu
        if show_main_menu:
            main_menu(con, main_menu_background_image, constants['screen_width'], constants['screen_height'])

            if show_load_error_message:
                message_box(con, 'No save game to load', 50, constants['screen_width'], constants['screen_height'])

            tcod.console_flush()

            action = handle_main_menu(key)

            # Actions for main menu
            new_game = action.get('new_game')
            load_saved_game = action.get('load_game')
            fullscreen = action.get('fullscreen')
            exit_game = action.get('exit')

            if show_load_error_message and (new_game or load_saved_game or exit_game):
                show_load_error_message = False

            # Starts a new game
            elif new_game:
                # Loads in player, inventory, map, and other such variables then sets turn to player
                player, entities, game_map, message_log, game_state = get_game_variables(constants)
                game_state = GameStates.PLAYERS_TURN

                show_main_menu = False

            # Loads a saved game
            elif load_saved_game:
                try:
                    player, entities, game_map, message_log, game_state = load_game()
                    show_main_menu = False
                except FileNotFoundError:
                    show_load_error_message = True

            # Exits game
            elif exit_game:
                break

            # Toggles fullscreen
            elif fullscreen:
                tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

        else:
            tcod.console_clear(con)
            play_game(player, entities, game_map, message_log, game_state, con, panel, constants)

            show_main_menu = True


if __name__ == '__main__':
    main()
