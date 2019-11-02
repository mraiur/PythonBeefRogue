from enum import Enum

"""
    GameStates Enums to determine turns and player death
"""

class GameStates(Enum):
    PLAYERS_TURN = 1
    ENEMY_TURN = 2
    PLAYER_DEAD = 3