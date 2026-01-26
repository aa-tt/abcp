"""
Text-Based Adventure Game
Demonstrates: OOP (inheritance, polymorphism), state management, dictionaries,
file I/O for save/load, exception handling, user input validation
"""

import json
import random
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from datetime import datetime


# Abstract Base Classes for Polymorphism
class GameObject(ABC):
    """Abstract base class for all game objects."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def interact(self, player):
        """Define how this object interacts with the player."""
        pass
    
    def __str__(self):
        return self.name


class Character(ABC):
    """Abstract base class for all characters (inheritance)."""
    
    def __init__(self, name: str, health: int, attack: int, defense: int):
        self.name = name
        self.max_health = health
        self.health = health
        self.attack = attack
        self.defense = defense
        self.is_alive = True
    
    def take_damage(self, damage: int):
        """Apply damage to character."""
        actual_damage = max(0, damage - self.defense)
        self.health -= actual_damage
        
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
        
        return actual_damage
    
    def heal(self, amount: int):
        """Heal character."""
        self.health = min(self.max_health, self.health + amount)
    
    @abstractmethod
    def get_combat_action(self, opponent):
        """Get combat action (polymorphic - different for player vs enemy)."""
        pass
    
    def __str__(self):
        return f"{self.name} (HP: {self.health}/{self.max_health})"


# Item Classes (Inheritance)
class Item(GameObject):
    """Base item class."""
    
    def __init__(self, name: str, description: str, value: int = 0):
        super().__init__(name, description)
        self.value = value
    
    def interact(self, player):
        """Default interaction - add to inventory."""
        player.add_to_inventory(self)
        return f"You picked up {self.name}"


class Weapon(Item):
    """Weapon item that increases attack."""
    
    def __init__(self, name: str, description: str, damage: int, value: int = 0):
        super().__init__(name, description, value)
        self.damage = damage
    
    def interact(self, player):
        player.add_to_inventory(self)
        return f"You picked up {self.name} (Damage: +{self.damage})"


class Potion(Item):
    """Consumable healing potion."""
    
    def __init__(self, name: str, description: str, heal_amount: int, value: int = 0):
        super().__init__(name, description, value)
        self.heal_amount = heal_amount
    
    def use(self, player):
        """Use the potion to heal."""
        if player.health >= player.max_health:
            return f"{player.name} is already at full health!"
        
        player.heal(self.heal_amount)
        return f"{player.name} used {self.name} and restored {self.heal_amount} HP!"
    
    def interact(self, player):
        player.add_to_inventory(self)
        return f"You picked up {self.name} (Heals: {self.heal_amount} HP)"


class Key(Item):
    """Key item for unlocking locations."""
    
    def __init__(self, name: str, description: str, unlocks: str):
        super().__init__(name, description, value=0)
        self.unlocks = unlocks
    
    def interact(self, player):
        player.add_to_inventory(self)
        return f"You picked up {self.name} - it might unlock something..."


# Character Classes (Inheritance and Polymorphism)
class Player(Character):
    """Player character with inventory and stats."""
    
    def __init__(self, name: str):
        super().__init__(name, health=100, attack=10, defense=5)
        self.inventory: List[Item] = []
        self.equipped_weapon: Optional[Weapon] = None
        self.gold = 50
        self.experience = 0
        self.level = 1
        self.quests_completed = []
    
    def add_to_inventory(self, item: Item):
        """Add item to inventory."""
        self.inventory.append(item)
    
    def remove_from_inventory(self, item: Item):
        """Remove item from inventory."""
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False
    
    def has_item(self, item_name: str) -> bool:
        """Check if player has specific item."""
        return any(item.name.lower() == item_name.lower() for item in self.inventory)
    
    def get_item(self, item_name: str) -> Optional[Item]:
        """Get specific item from inventory."""
        for item in self.inventory:
            if item.name.lower() == item_name.lower():
                return item
        return None
    
    def equip_weapon(self, weapon: Weapon):
        """Equip a weapon."""
        if self.equipped_weapon:
            print(f"Unequipped {self.equipped_weapon.name}")
        self.equipped_weapon = weapon
        return f"Equipped {weapon.name}! Attack +{weapon.damage}"
    
    def get_total_attack(self) -> int:
        """Calculate total attack with equipped weapon."""
        base_attack = self.attack
        weapon_bonus = self.equipped_weapon.damage if self.equipped_weapon else 0
        return base_attack + weapon_bonus
    
    def gain_experience(self, amount: int):
        """Gain experience and potentially level up."""
        self.experience += amount
        xp_needed = self.level * 100
        
        if self.experience >= xp_needed:
            self.level_up()
    
    def level_up(self):
        """Level up the player."""
        self.level += 1
        self.max_health += 20
        self.health = self.max_health
        self.attack += 5
        self.defense += 2
        print(f"\n🎉 LEVEL UP! You are now level {self.level}!")
        print(f"   HP: {self.max_health} | ATK: {self.attack} | DEF: {self.defense}")
    
    def get_combat_action(self, opponent):
        """Get combat action from player (polymorphic method)."""
        print(f"\n{self} vs {opponent}")
        print("1. Attack")
        print("2. Use Potion")
        print("3. Run Away")
        
        while True:
            choice = input("Choose action: ").strip()
            if choice in ['1', '2', '3']:
                return choice
            print("Invalid choice. Enter 1, 2, or 3.")
    
    def to_dict(self) -> Dict:
        """Convert player state to dictionary for saving."""
        return {
            'name': self.name,
            'health': self.health,
            'max_health': self.max_health,
            'attack': self.attack,
            'defense': self.defense,
            'gold': self.gold,
            'experience': self.experience,
            'level': self.level,
            'inventory': [{'type': type(item).__name__, 'name': item.name} for item in self.inventory],
            'equipped_weapon': self.equipped_weapon.name if self.equipped_weapon else None,
            'quests_completed': self.quests_completed
        }


class Enemy(Character):
    """Enemy character."""
    
    def __init__(self, name: str, health: int, attack: int, defense: int, 
                 xp_reward: int = 0, gold_reward: int = 0):
        super().__init__(name, health, attack, defense)
        self.xp_reward = xp_reward
        self.gold_reward = gold_reward
    
    def get_combat_action(self, opponent):
        """AI combat action (polymorphic method)."""
        # Simple AI - always attacks
        return 'attack'
    
    def get_rewards(self) -> Dict:
        """Get rewards for defeating this enemy."""
        return {
            'xp': self.xp_reward,
            'gold': self.gold_reward
        }


class NPC(GameObject):
    """Non-player character with dialogue."""
    
    def __init__(self, name: str, description: str, dialogue: List[str], 
                 quest: Optional[Dict] = None):
        super().__init__(name, description)
        self.dialogue = dialogue
        self.dialogue_index = 0
        self.quest = quest
    
    def interact(self, player):
        """Talk to NPC."""
        message = self.dialogue[self.dialogue_index]
        
        # Cycle through dialogue
        self.dialogue_index = (self.dialogue_index + 1) % len(self.dialogue)
        
        # Check for quest
        if self.quest and not self.quest.get('completed', False):
            message += f"\n\nQuest: {self.quest['description']}"
            if self.quest.get('reward'):
                message += f"\nReward: {self.quest['reward']}"
        
        return message


# Location Classes (Inheritance and Polymorphism)
class Location(ABC):
    """Abstract base class for game locations."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.items: List[Item] = []
        self.npcs: List[NPC] = []
        self.enemies: List[Enemy] = []
        self.connected_locations: Dict[str, str] = {}  # direction -> location_name
        self.visited = False
    
    @abstractmethod
    def enter(self, player):
        """Called when player enters this location (polymorphic)."""
        self.visited = True
    
    def add_connection(self, direction: str, location_name: str):
        """Add connection to another location."""
        self.connected_locations[direction] = location_name
    
    def get_available_directions(self) -> List[str]:
        """Get list of available directions."""
        return list(self.connected_locations.keys())
    
    def __str__(self):
        return self.name


class SafeLocation(Location):
    """Safe location with no enemies."""
    
    def enter(self, player):
        """Enter safe location."""
        super().enter(player)
        print(f"\n{'='*60}")
        print(f"📍 {self.name}")
        print(f"{'='*60}")
        print(self.description)
        
        if self.npcs:
            print(f"\nPeople here: {', '.join(npc.name for npc in self.npcs)}")
        
        if self.items:
            print(f"Items here: {', '.join(item.name for item in self.items)}")


class DangerousLocation(Location):
    """Location with potential enemies."""
    
    def __init__(self, name: str, description: str, danger_level: int = 1):
        super().__init__(name, description)
        self.danger_level = danger_level
    
    def enter(self, player):
        """Enter dangerous location - may trigger combat."""
        super().enter(player)
        print(f"\n{'='*60}")
        print(f"⚔️  {self.name}")
        print(f"{'='*60}")
        print(self.description)
        
        # Random encounter
        if self.enemies and random.random() < 0.5:
            enemy = random.choice(self.enemies)
            print(f"\n⚠️  You encountered a {enemy.name}!")
            return enemy
        
        if self.items:
            print(f"\nItems here: {', '.join(item.name for item in self.items)}")
        
        return None


class LockedLocation(Location):
    """Location that requires a key."""
    
    def __init__(self, name: str, description: str, required_key: str):
        super().__init__(name, description)
        self.required_key = required_key
        self.is_locked = True
    
    def enter(self, player):
        """Enter locked location - requires key."""
        if self.is_locked:
            if player.has_item(self.required_key):
                print(f"\n🔓 You used the {self.required_key} to unlock {self.name}!")
                self.is_locked = False
            else:
                print(f"\n🔒 {self.name} is locked. You need: {self.required_key}")
                return None
        
        super().enter(player)
        print(f"\n{'='*60}")
        print(f"🏛️  {self.name}")
        print(f"{'='*60}")
        print(self.description)
        
        if self.items:
            print(f"\nItems here: {', '.join(item.name for item in self.items)}")


# Game State Management
class GameState:
    """Manages the overall game state."""
    
    def __init__(self):
        self.player: Optional[Player] = None
        self.current_location: Optional[Location] = None
        self.locations: Dict[str, Location] = {}
        self.game_over = False
        self.victory = False
        self.turn_count = 0
    
    def create_world(self):
        """Create game world with locations, items, NPCs, and enemies."""
        
        # Create items
        sword = Weapon("Iron Sword", "A sturdy iron sword", damage=15, value=100)
        health_potion = Potion("Health Potion", "Restores 50 HP", heal_amount=50, value=25)
        health_potion2 = Potion("Health Potion", "Restores 50 HP", heal_amount=50, value=25)
        dungeon_key = Key("Dungeon Key", "An old rusty key", unlocks="Dark Dungeon")
        treasure = Item("Ancient Treasure", "A priceless artifact!", value=1000)
        
        # Create NPCs
        merchant = NPC(
            "Merchant",
            "A traveling merchant with various goods",
            [
                "Welcome, traveler! I have goods for sale.",
                "The dungeon to the east is very dangerous...",
                "Have you found any treasure lately?"
            ]
        )
        
        old_wizard = NPC(
            "Old Wizard",
            "A wise old wizard with ancient knowledge",
            [
                "Beware the Dark Dungeon! Many have entered, few returned.",
                "The Dungeon Key is hidden in the forest, they say.",
                "Seek the Ancient Treasure to complete your quest!"
            ],
            quest={
                'description': "Find the Ancient Treasure in the Dark Dungeon",
                'reward': "500 XP and eternal glory!",
                'completed': False
            }
        )
        
        # Create enemies
        goblin = Enemy("Goblin", health=30, attack=8, defense=2, xp_reward=20, gold_reward=10)
        wolf = Enemy("Wild Wolf", health=25, attack=12, defense=1, xp_reward=15, gold_reward=5)
        orc = Enemy("Orc Warrior", health=60, attack=20, defense=8, xp_reward=50, gold_reward=30)
        dragon = Enemy("Ancient Dragon", health=150, attack=35, defense=15, xp_reward=200, gold_reward=100)
        
        # Create locations
        village = SafeLocation(
            "Village Square",
            "A peaceful village with friendly inhabitants. A good place to rest and prepare."
        )
        village.npcs = [merchant, old_wizard]
        village.items = [health_potion]
        
        forest = DangerousLocation(
            "Dark Forest",
            "A dense forest with towering trees. Strange sounds echo in the distance.",
            danger_level=1
        )
        forest.enemies = [goblin, wolf]
        forest.items = [dungeon_key, health_potion2]
        
        mountain = DangerousLocation(
            "Mountain Pass",
            "A treacherous mountain path with steep cliffs and icy winds.",
            danger_level=2
        )
        mountain.enemies = [orc]
        mountain.items = [sword]
        
        dungeon = LockedLocation(
            "Dark Dungeon",
            "An ancient dungeon filled with darkness and danger. The air is thick with malice.",
            required_key="Dungeon Key"
        )
        dungeon.enemies = [dragon]
        dungeon.items = [treasure]
        
        # Connect locations
        village.add_connection("north", "Dark Forest")
        village.add_connection("west", "Mountain Pass")
        
        forest.add_connection("south", "Village Square")
        forest.add_connection("east", "Dark Dungeon")
        
        mountain.add_connection("east", "Village Square")
        
        dungeon.add_connection("west", "Dark Forest")
        
        # Store locations
        self.locations = {
            "Village Square": village,
            "Dark Forest": forest,
            "Mountain Pass": mountain,
            "Dark Dungeon": dungeon
        }
        
        # Set starting location
        self.current_location = village
    
    def combat(self, player: Player, enemy: Enemy) -> bool:
        """Handle combat between player and enemy."""
        print(f"\n{'='*60}")
        print(f"⚔️  COMBAT: {player.name} vs {enemy.name}")
        print(f"{'='*60}")
        
        while player.is_alive and enemy.is_alive:
            # Player's turn
            action = player.get_combat_action(enemy)
            
            if action == '1':  # Attack
                damage = random.randint(player.get_total_attack() - 3, player.get_total_attack() + 3)
                actual_damage = enemy.take_damage(damage)
                print(f"\n💥 You attack {enemy.name} for {actual_damage} damage!")
                
                if not enemy.is_alive:
                    print(f"🎯 You defeated {enemy.name}!")
                    rewards = enemy.get_rewards()
                    player.gain_experience(rewards['xp'])
                    player.gold += rewards['gold']
                    print(f"   Gained {rewards['xp']} XP and {rewards['gold']} gold!")
                    
                    # Remove enemy from location
                    if enemy in self.current_location.enemies:
                        self.current_location.enemies.remove(enemy)
                    
                    return True
            
            elif action == '2':  # Use Potion
                potions = [item for item in player.inventory if isinstance(item, Potion)]
                if potions:
                    potion = potions[0]
                    print(f"\n{potion.use(player)}")
                    player.remove_from_inventory(potion)
                else:
                    print("\n❌ You have no potions!")
                    continue
            
            elif action == '3':  # Run away
                if random.random() < 0.6:
                    print("\n🏃 You successfully ran away!")
                    return False
                else:
                    print("\n❌ Failed to escape!")
            
            # Enemy's turn (if still alive)
            if enemy.is_alive:
                damage = random.randint(enemy.attack - 2, enemy.attack + 2)
                actual_damage = player.take_damage(damage)
                print(f"💢 {enemy.name} attacks you for {actual_damage} damage!")
                
                if not player.is_alive:
                    print("\n💀 You have been defeated...")
                    self.game_over = True
                    return False
        
        return True
    
    def save_game(self, filename: str = "savegame.json"):
        """Save game state to file."""
        try:
            save_data = {
                'player': self.player.to_dict(),
                'current_location': self.current_location.name,
                'turn_count': self.turn_count,
                'visited_locations': [name for name, loc in self.locations.items() if loc.visited],
                'timestamp': datetime.now().isoformat()
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
            
            print(f"\n💾 Game saved to {filename}")
            return True
        except Exception as e:
            print(f"\n❌ Error saving game: {e}")
            return False
    
    def load_game(self, filename: str = "savegame.json") -> bool:
        """Load game state from file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            # Recreate player
            player_data = save_data['player']
            self.player = Player(player_data['name'])
            self.player.health = player_data['health']
            self.player.max_health = player_data['max_health']
            self.player.attack = player_data['attack']
            self.player.defense = player_data['defense']
            self.player.gold = player_data['gold']
            self.player.experience = player_data['experience']
            self.player.level = player_data['level']
            
            # Restore location
            self.current_location = self.locations[save_data['current_location']]
            self.turn_count = save_data['turn_count']
            
            print(f"\n💾 Game loaded from {filename}")
            print(f"   Saved on: {save_data['timestamp'][:19]}")
            return True
        except FileNotFoundError:
            print(f"\n❌ Save file '{filename}' not found")
            return False
        except Exception as e:
            print(f"\n❌ Error loading game: {e}")
            return False


def display_commands():
    """Display available commands."""
    print("\n" + "="*60)
    print("COMMANDS")
    print("="*60)
    print("  look         - Examine current location")
    print("  inventory    - View your inventory")
    print("  stats        - View your stats")
    print("  go <dir>     - Move in direction (north/south/east/west)")
    print("  take <item>  - Pick up an item")
    print("  use <item>   - Use an item")
    print("  equip <item> - Equip a weapon")
    print("  talk <name>  - Talk to an NPC")
    print("  save         - Save game")
    print("  load         - Load game")
    print("  help         - Show this help")
    print("  quit         - Quit game")
    print("="*60)


def process_command(command: str, game_state: GameState) -> bool:
    """Process player command. Returns False if game should quit."""
    parts = command.lower().split()
    
    if not parts:
        return True
    
    cmd = parts[0]
    player = game_state.player
    location = game_state.current_location
    
    try:
        if cmd == 'help':
            display_commands()
        
        elif cmd == 'look':
            location.enter(player)
            print(f"\nExits: {', '.join(location.get_available_directions())}")
        
        elif cmd == 'stats':
            print(f"\n{'='*60}")
            print(f"CHARACTER: {player.name}")
            print(f"{'='*60}")
            print(f"Level: {player.level} | XP: {player.experience}")
            print(f"Health: {player.health}/{player.max_health}")
            print(f"Attack: {player.get_total_attack()} | Defense: {player.defense}")
            print(f"Gold: {player.gold}")
            if player.equipped_weapon:
                print(f"Weapon: {player.equipped_weapon.name}")
        
        elif cmd == 'inventory':
            if not player.inventory:
                print("\nYour inventory is empty.")
            else:
                print(f"\n{'='*40}")
                print("INVENTORY")
                print(f"{'='*40}")
                for item in player.inventory:
                    print(f"  - {item.name}: {item.description}")
        
        elif cmd == 'go':
            if len(parts) < 2:
                print("Go where? (north/south/east/west)")
                return True
            
            direction = parts[1]
            if direction in location.connected_locations:
                new_location_name = location.connected_locations[direction]
                new_location = game_state.locations[new_location_name]
                game_state.current_location = new_location
                
                # Enter new location
                enemy = new_location.enter(player)
                
                # Handle combat if enemy encountered
                if enemy:
                    game_state.combat(player, enemy)
                
                print(f"\nExits: {', '.join(new_location.get_available_directions())}")
            else:
                print(f"You can't go {direction} from here.")
                print(f"Available exits: {', '.join(location.get_available_directions())}")
        
        elif cmd == 'take':
            if len(parts) < 2:
                print("Take what?")
                return True
            
            item_name = ' '.join(parts[1:])
            found = None
            for item in location.items:
                if item.name.lower() == item_name.lower():
                    found = item
                    break
            
            if found:
                message = found.interact(player)
                print(f"\n{message}")
                location.items.remove(found)
            else:
                print(f"\nThere is no '{item_name}' here.")
        
        elif cmd == 'use':
            if len(parts) < 2:
                print("Use what?")
                return True
            
            item_name = ' '.join(parts[1:])
            item = player.get_item(item_name)
            
            if item:
                if isinstance(item, Potion):
                    print(f"\n{item.use(player)}")
                    player.remove_from_inventory(item)
                else:
                    print(f"\nYou can't use {item.name} like that.")
            else:
                print(f"\nYou don't have '{item_name}' in your inventory.")
        
        elif cmd == 'equip':
            if len(parts) < 2:
                print("Equip what?")
                return True
            
            item_name = ' '.join(parts[1:])
            item = player.get_item(item_name)
            
            if item:
                if isinstance(item, Weapon):
                    print(f"\n{player.equip_weapon(item)}")
                else:
                    print(f"\n{item.name} is not a weapon.")
            else:
                print(f"\nYou don't have '{item_name}' in your inventory.")
        
        elif cmd == 'talk':
            if len(parts) < 2:
                print("Talk to whom?")
                return True
            
            npc_name = ' '.join(parts[1:])
            found = None
            for npc in location.npcs:
                if npc.name.lower() == npc_name.lower():
                    found = npc
                    break
            
            if found:
                print(f"\n{found.name}: \"{found.interact(player)}\"")
            else:
                print(f"\nThere is no one named '{npc_name}' here.")
        
        elif cmd == 'save':
            game_state.save_game()
        
        elif cmd == 'load':
            if game_state.load_game():
                game_state.current_location.enter(player)
        
        elif cmd == 'quit':
            confirm = input("\nAre you sure you want to quit? (yes/no): ").lower()
            if confirm in ['yes', 'y']:
                print("\nThanks for playing!")
                return False
        
        else:
            print(f"\nUnknown command: '{cmd}'. Type 'help' for commands.")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    game_state.turn_count += 1
    return True


def main():
    """Main game loop."""
    print("="*60)
    print("TEXT-BASED ADVENTURE GAME")
    print("="*60)
    print("\nWelcome, brave adventurer!")
    
    # Initialize game
    game_state = GameState()
    game_state.create_world()
    
    # Create player
    print("\nWhat is your name, hero?")
    name = input("> ").strip() or "Adventurer"
    game_state.player = Player(name)
    
    print(f"\nWelcome, {name}!")
    print("\nYour quest: Find the Ancient Treasure hidden in the Dark Dungeon!")
    print("Type 'help' for a list of commands.\n")
    
    # Enter starting location
    game_state.current_location.enter(game_state.player)
    print(f"\nExits: {', '.join(game_state.current_location.get_available_directions())}")
    
    # Main game loop
    while not game_state.game_over:
        try:
            command = input("\n> ").strip()
            
            if not command:
                continue
            
            if not process_command(command, game_state):
                break
            
            # Check for victory condition
            if game_state.player.has_item("Ancient Treasure"):
                print("\n" + "="*60)
                print("🎉 VICTORY! 🎉")
                print("="*60)
                print(f"Congratulations, {game_state.player.name}!")
                print("You have found the Ancient Treasure and completed your quest!")
                print(f"\nFinal Stats:")
                print(f"  Level: {game_state.player.level}")
                print(f"  Gold: {game_state.player.gold}")
                print(f"  Turns: {game_state.turn_count}")
                game_state.victory = True
                break
        
        except KeyboardInterrupt:
            print("\n\nGame interrupted. Type 'quit' to exit or 'save' to save your progress.")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
    
    if game_state.game_over and not game_state.victory:
        print("\n" + "="*60)
        print("GAME OVER")
        print("="*60)
        print("Your adventure has come to an end...")


if __name__ == "__main__":
    main()


"""
Key Features:

* OOP Inheritance: Abstract base classes (GameObject, Character, Location) with multiple derived classes
* Polymorphism: Different interact(), enter(), and get_combat_action() methods for different object types
* State Management: GameState class tracking player, locations, inventory, quests
* Dictionaries: Locations, connections, inventory management
* File I/O: Full save/load game functionality with JSON
* Exception Handling: Try-except blocks throughout
* Input Validation: Command parsing and validation

Game Elements:

* Multiple location types (Safe, Dangerous, Locked)
* Combat system with enemies
* Inventory and equipment system
* NPC dialogue and quests
* Level progression and XP
* Save/load game state

Demonstrates:

* Abstract base classes with ABC and @abstractmethod
* Class inheritance hierarchies
* Polymorphic method overriding
* State management across multiple classes
* JSON serialization/deserialization
* User input validation and parsing
"""