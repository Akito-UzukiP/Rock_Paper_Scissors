import pygame
import numpy as np
import random
import sys
import math
import time
from scipy.spatial import cKDTree
from shapely.geometry import Point, Polygon

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 960, 960
FPS = 144
MAX_TIME = 3000  # frames before declaring a draw
BACKGROUND_COLOR = (30, 30, 30)

# Obstacle settings
NUM_OBSTACLES = 5
OBSTACLE_COLOR = (80, 80, 80)
OBSTACLE_REPULSION = 2.0
OBSTACLE_REPULSION_DISTANCE = 50

# Center attraction to avoid edge clustering
CENTER_ATTRACTION = True
CENTER_FORCE = 0.9
CENTER_X, CENTER_Y = WIDTH / 2, HEIGHT / 2

# Group behavior variables
GROUP_BEHAVIOR = True
GROUP_COHESION = 0.1   # Reduced cohesion
GROUP_ALIGNMENT = 0.1
GROUP_RADIUS = 100
GROUP_SEPARATION = 0.82  # Separation force strength
GROUP_MIN_DISTANCE = 30  # Maintain this minimum distance between units

# Unit properties
UNIT_RADIUS = 5
UNIT_SPEED = 2
BASE_SPEED = 2  # Normal speed for reference
SCISSORS_COLOR = (255, 0, 0)      # Red
ROCK_COLOR = (100, 100, 100)      # Gray
PAPER_COLOR = (0, 0, 255)         # Blue
MIN_DISTANCE = UNIT_RADIUS * 2    # Minimum distance to count as collision
REPULSION_FACTOR = 4.0            # Increased repulsion force
REPULSION_RADIUS = 150            # Radius within which repulsion occurs
RANDOM_MOVEMENT = 0.5             # Increased random movement
COLLISION_CHANCE = 0.3            # Reduced probability of type change on collision
SHOW_ATTRACTIONS = False          # Whether to show attraction/repulsion lines

# # Ability settings
# ABILITY_COOLDOWN = 200            # Frames between ability uses
# TELEPORT_DISTANCE = 150           # Distance for scissors teleport
# SPEED_BOOST_FACTOR = 2.5          # Speed multiplier for rock boost
# SPEED_BOOST_DURATION = 60         # Frames for speed boost
# REPULSION_BOOST_FACTOR = 5.0      # Strength of paper's repulsion ability
# REPULSION_BOOST_RADIUS = 100      # Radius for paper's repulsion
# REPULSION_BOOST_DURATION = 20     # Frames for repulsion boost
# ABILITY_CHANCE = 0.005            # Chance to use ability each frame

# Initialize screen
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rock Paper Scissors Simulation")
clock = pygame.time.Clock()

class Obstacle:
    def __init__(self):
        # Generate a random polygon with 3-7 vertices
        num_vertices = random.randint(3, 7)
        center_x = random.randint(100, WIDTH - 100)
        center_y = random.randint(100, HEIGHT - 100)
        
        # Generate random vertices around the center
        radius = random.randint(30, 70)
        vertices = []
        for i in range(num_vertices):
            angle = 2 * math.pi * i / num_vertices
            # Add some randomness to the angle
            angle += random.uniform(-0.2, 0.2)
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            vertices.append((x, y))
        
        self.vertices = vertices
        self.polygon = Polygon(vertices)
    
    def draw(self):
        pygame.draw.polygon(screen, OBSTACLE_COLOR, self.vertices)
        
    def distance_to_point(self, point_x, point_y):
        """Calculate minimum distance from point to polygon"""
        point = Point(point_x, point_y)
        
        # If point is inside polygon, return 0
        if self.polygon.contains(point):
            return 0
            
        # Return distance to closest edge
        return self.polygon.exterior.distance(point)

class SpatialTree:
    """A wrapper around scipy's KDTree for efficient spatial queries"""
    def __init__(self, units):
        # Extract positions and build tree
        self.units = units
        positions = np.array([[unit.x, unit.y] for unit in units])
        self.tree = cKDTree(positions)
        
    def query_radius(self, unit, radius):
        """Find all units within radius of the given unit"""
        query_point = np.array([unit.x, unit.y])
        indices = self.tree.query_ball_point(query_point, radius)
        return [self.units[i] for i in indices if self.units[i] != unit]
        
    def query_by_type(self, unit, radius, unit_type):
        """Find all units of a specific type within radius"""
        nearby = self.query_radius(unit, radius)
        return [u for u in nearby if u.unit_type == unit_type]
    
    def find_nearest_of_type(self, unit, unit_type, k=3):
        """Find k nearest units of specific type to the given unit"""
        # Get all units of this type
        type_units = [u for u in self.units if u.unit_type == unit_type and u != unit]
        if not type_units:
            return []
            
        # Extract their positions
        positions = np.array([[u.x, u.y] for u in type_units])
        query_point = np.array([unit.x, unit.y])
        
        # Find nearest k
        if len(positions) < k:
            k = len(positions)
            
        # Query the distances and indices of nearest neighbors
        if len(positions) > 0:
            distances, indices = cKDTree(positions).query(query_point, k=k)
            
            # If only one result, wrap in lists
            if k == 1:
                distances = [distances]
                indices = [indices]
                
            # Return units with their distances
            results = []
            for i, dist in zip(indices, distances):
                results.append((type_units[i], dist))
                
            return results
        return []

class Unit:
    def __init__(self, unit_type, x, y):
        self.unit_type = unit_type  # 0: Scissors, 1: Rock, 2: Paper
        self.x = x
        self.y = y
        self.target = None
        self.vx = 0
        self.vy = 0
        
    def draw(self):
        if self.unit_type == 0:  # Scissors
            color = SCISSORS_COLOR
        elif self.unit_type == 1:  # Rock
            color = ROCK_COLOR
        else:  # Paper
            color = PAPER_COLOR
            
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), UNIT_RADIUS)
        
        # Draw attraction line to target
        if SHOW_ATTRACTIONS and self.target is not None:
            # Draw a line to target (prey) - green line
            pygame.draw.line(screen, (0, 200, 0), 
                            (int(self.x), int(self.y)),
                            (int(self.target.x), int(self.target.y)), 1)
        
    def find_target(self, spatial_tree):
        # Scissors (0) target Paper (2)
        # Rock (1) targets Scissors (0)
        # Paper (2) targets Rock (1)
        target_type = (self.unit_type + 2) % 3
        
        # Find nearest targets using spatial tree
        potential_targets = spatial_tree.find_nearest_of_type(self, target_type, k=3)
        
        if not potential_targets:
            return None
            
        # Select randomly from the closest 3 targets (or fewer if not enough)
        num_choices = len(potential_targets)
        if num_choices > 0:
            # 95% chance to pick the closest, 5% to pick one of the next two closest
            if random.random() < 0.95 or num_choices == 1:
                return potential_targets[0][0]
            else:
                return potential_targets[random.randint(1, num_choices-1)][0]
        
        return None
        
    def find_threats(self, spatial_tree):
        # Scissors (0) threatened by Rock (1)
        # Rock (1) threatened by Paper (2)
        # Paper (2) threatened by Scissors (0)
        predator_type = (self.unit_type + 1) % 3
        
        # Get all predators within repulsion radius
        nearby = spatial_tree.query_by_type(self, REPULSION_RADIUS, predator_type)
        
        # Calculate distances
        threats = []
        for unit in nearby:
            distance = math.sqrt((self.x - unit.x) ** 2 + (self.y - unit.y) ** 2)
            threats.append((unit, distance))
        
        return threats
    
    def find_same_type_neighbors(self, spatial_tree, radius):
        """Find units of the same type within a certain radius using spatial tree."""
        return spatial_tree.query_by_type(self, radius, self.unit_type)
        
    def move_towards_target(self, spatial_tree):
        # Initialize velocity
        self.vx = 0
        self.vy = 0
        
        # Attraction to target
        if self.target is not None:
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            distance = math.sqrt(dx ** 2 + dy ** 2)
            
            if distance > 0:
                # Attraction force - weaker than repulsion
                attraction_strength = max(0.7, 1 - REPULSION_FACTOR/2)  # Even weaker than before
                self.vx = (dx / distance) * UNIT_SPEED * attraction_strength
                self.vy = (dy / distance) * UNIT_SPEED * attraction_strength
        
        # Repulsion from threats
        threats = self.find_threats(spatial_tree)
        for threat, distance in threats:
            if distance > 0:
                # Calculate repulsion vector - away from threat
                dx = self.x - threat.x
                dy = self.y - threat.y
                
                # Scale repulsion by distance (closer = stronger)
                repulsion_strength = REPULSION_FACTOR * (1 - distance / REPULSION_RADIUS)
                
                # Apply repulsion force
                self.vx += (dx / distance) * repulsion_strength
                self.vy += (dy / distance) * repulsion_strength
                
                # Draw repulsion line if showing attractions
                if SHOW_ATTRACTIONS:
                    # Draw a thin red line to threats
                    pygame.draw.line(screen, (200, 0, 0), 
                                    (int(self.x), int(self.y)),
                                    (int(threat.x), int(threat.y)), 1)
                                    
        # Group behavior - cohesion, alignment, and separation with same type
        if GROUP_BEHAVIOR:
            neighbors = self.find_same_type_neighbors(spatial_tree, GROUP_RADIUS)
            if neighbors:
                # Separation - avoid crowding neighbors
                sep_x, sep_y = 0, 0
                sep_count = 0
                
                for neighbor in neighbors:
                    # Calculate distance to neighbor
                    dx = self.x - neighbor.x
                    dy = self.y - neighbor.y
                    distance = math.sqrt(dx**2 + dy**2)
                    
                    # Apply separation when too close
                    if distance < GROUP_MIN_DISTANCE and distance > 0:
                        # The closer, the stronger the separation
                        separation_factor = 1.0 - (distance / GROUP_MIN_DISTANCE)
                        sep_x += (dx / distance) * separation_factor
                        sep_y += (dy / distance) * separation_factor
                        sep_count += 1
                
                # Apply separation force if any neighbors are too close
                if sep_count > 0:
                    self.vx += sep_x * GROUP_SEPARATION
                    self.vy += sep_y * GROUP_SEPARATION
                    
                    # Visualize separation with white lines
                    if SHOW_ATTRACTIONS and sep_count > 0:
                        # Draw a white line showing separation force
                        end_x = self.x + sep_x * 10  # Amplify for visibility
                        end_y = self.y + sep_y * 10
                        pygame.draw.line(screen, (255, 255, 255), 
                                        (int(self.x), int(self.y)),
                                        (int(end_x), int(end_y)), 1)
                
                # Cohesion - move toward center of mass of neighbors (if not too close)
                center_x = sum(unit.x for unit in neighbors) / len(neighbors)
                center_y = sum(unit.y for unit in neighbors) / len(neighbors)
                
                if center_x != self.x or center_y != self.y:  # Avoid division by zero
                    dx = center_x - self.x
                    dy = center_y - self.y
                    distance = math.sqrt(dx ** 2 + dy ** 2)
                    
                    # Only apply cohesion if not too close
                    if distance > GROUP_MIN_DISTANCE:
                        # Apply cohesion force
                        self.vx += (dx / distance) * GROUP_COHESION
                        self.vy += (dy / distance) * GROUP_COHESION
                
                # Alignment - align velocity with neighbors
                avg_vx = sum(unit.vx for unit in neighbors) / len(neighbors)
                avg_vy = sum(unit.vy for unit in neighbors) / len(neighbors)
                
                # Apply alignment force
                self.vx += avg_vx * GROUP_ALIGNMENT
                self.vy += avg_vy * GROUP_ALIGNMENT
                
                # Visualize group connections
                if SHOW_ATTRACTIONS and len(neighbors) > 0:
                    # Draw faint cyan lines to group members (up to 3)
                    for neighbor in neighbors[:min(3, len(neighbors))]:
                        # Only visualize connections to units we're not separating from
                        dx = self.x - neighbor.x
                        dy = self.y - neighbor.y
                        distance = math.sqrt(dx**2 + dy**2)
                        
                        if distance >= GROUP_MIN_DISTANCE:
                            pygame.draw.line(screen, (0, 150, 150), 
                                            (int(self.x), int(self.y)),
                                            (int(neighbor.x), int(neighbor.y)), 1)
        
        # Center attraction to prevent edge clustering
        if CENTER_ATTRACTION:
            dx = CENTER_X - self.x
            dy = CENTER_Y - self.y
            
            # Calculate distance from center
            distance = math.sqrt(dx ** 2 + dy ** 2)
            
            # Attraction increases with distance from center
            if distance > WIDTH / 4:  # Only apply when far from center
                # Calculate center attraction strength based on distance
                center_strength = CENTER_FORCE * (distance / (WIDTH/2))
                
                # Apply center attraction force
                if distance > 0:  # Avoid division by zero
                    self.vx += (dx / distance) * center_strength
                    self.vy += (dy / distance) * center_strength
        
        # Add random movement
        self.vx += (random.random() - 0.5) * RANDOM_MOVEMENT
        self.vy += (random.random() - 0.5) * RANDOM_MOVEMENT

        # --- 全局分离：强制避免所有单位重叠 ---
        # 获取所有单位，遍历并施加强分离力
        global all_units
        if 'all_units' in globals():
            sep_x, sep_y = 0, 0
            for other in all_units:
                if other is self:
                    continue
                dx = self.x - other.x
                dy = self.y - other.y
                dist = math.hypot(dx, dy)
                if dist < MIN_DISTANCE/1.05 and dist > 0:
                    # 强分离力，距离越近力越大
                    force = 20.0 * (MIN_DISTANCE - dist) / MIN_DISTANCE
                    sep_x += (dx / dist) * force
                    sep_y += (dy / dist) * force
            self.vx += sep_x
            self.vy += sep_y

        # Normalize velocity if it's too high
        speed = math.sqrt(self.vx ** 2 + self.vy ** 2)
        if speed > UNIT_SPEED:
            self.vx = (self.vx / speed) * UNIT_SPEED
            self.vy = (self.vy / speed) * UNIT_SPEED

        # Apply movement
        self.x += self.vx
        self.y += self.vy
        
        # Keep within bounds - bounce off edges instead of sticking
        if self.x < UNIT_RADIUS:
            self.x = UNIT_RADIUS
            self.vx *= -0.5  # Bounce with energy loss
        elif self.x > WIDTH - UNIT_RADIUS:
            self.x = WIDTH - UNIT_RADIUS
            self.vx *= -0.5  # Bounce with energy loss
            
        if self.y < UNIT_RADIUS:
            self.y = UNIT_RADIUS
            self.vy *= -0.5  # Bounce with energy loss
        elif self.y > HEIGHT - UNIT_RADIUS:
            self.y = HEIGHT - UNIT_RADIUS
            self.vy *= -0.5  # Bounce with energy loss
            
    def check_collision(self, spatial_tree):
        # Check collision with units that can beat this unit
        # Scissors (0) beaten by Rock (1)
        # Rock (1) beaten by Paper (2)
        # Paper (2) beaten by Scissors (0)
        predator_type = (self.unit_type + 1) % 3
        
        # Get nearby predators using spatial tree
        nearby_predators = spatial_tree.query_by_type(self, MIN_DISTANCE * 2, predator_type)
        
        for unit in nearby_predators:
            distance = math.sqrt((self.x - unit.x) ** 2 + (self.y - unit.y) ** 2)
            if distance < MIN_DISTANCE:
                # Only convert with a certain probability
                if random.random() < COLLISION_CHANCE:
                    return predator_type
        
        return None

def initialize_units(scissors_count, rock_count, paper_count):
    units = []
    total_count = scissors_count + rock_count + paper_count
    
    # Generate random positions for all units at once (vectorized)
    positions = np.random.uniform(
        low=[UNIT_RADIUS, UNIT_RADIUS], 
        high=[WIDTH - UNIT_RADIUS, HEIGHT - UNIT_RADIUS],
        size=(total_count, 2)
    )
    
    # Add scissors
    for i in range(scissors_count):
        units.append(Unit(0, positions[i][0], positions[i][1]))
    
    # Add rocks
    for i in range(scissors_count, scissors_count + rock_count):
        units.append(Unit(1, positions[i][0], positions[i][1]))
    
    # Add papers
    for i in range(scissors_count + rock_count, total_count):
        units.append(Unit(2, positions[i][0], positions[i][1]))
    
    return units

def check_end_condition(units):
    if not units:
        return True
    
    # Vectorized check if all units are the same type
    unit_types = np.array([unit.unit_type for unit in units])
    return np.all(unit_types == unit_types[0])

def main():
    # Get initial counts from command line arguments or use defaults
    scissors_count = 80
    rock_count = 80
    paper_count = 80

    if len(sys.argv) >= 4:
        scissors_count = int(sys.argv[1])
        rock_count = int(sys.argv[2])
        paper_count = int(sys.argv[3])

    units = initialize_units(scissors_count, rock_count, paper_count)
    global all_units
    all_units = units  # 供全局分离机制使用
    running = True
    
    # For max time limit
    time_steps = 0
    status_message = "Running..."
    fps_timer = time.time()
    frame_count = 0
    
    while running:
        start_time = time.time()
        
        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        # Performance measurement - start timer for tree creation
        tree_start_time = time.time()
        
        # Create spatial tree for this frame
        spatial_tree = SpatialTree(units)
        
        tree_time = time.time() - tree_start_time
        
        # Performance measurement - start timer for target finding
        target_start_time = time.time()
        
        # Update targets using spatial tree
        for unit in units:
            unit.target = unit.find_target(spatial_tree)
            
        target_time = time.time() - target_start_time
        
        # Performance measurement - start timer for movement
        move_start_time = time.time()
        
        # Update positions using spatial tree
        for unit in units:
            unit.move_towards_target(spatial_tree)
            
        move_time = time.time() - move_start_time
        
        # Check collisions and convert units
        new_types = {}
        for i, unit in enumerate(units):
            new_type = unit.check_collision(spatial_tree)
            if new_type is not None:
                new_types[i] = new_type
        
        for i, new_type in new_types.items():
            units[i].unit_type = new_type
        
        # Time limit check
        time_steps += 1
        if time_steps >= MAX_TIME:
            # Determine which type has the most units
            scissors_remaining = sum(1 for unit in units if unit.unit_type == 0)
            rock_remaining = sum(1 for unit in units if unit.unit_type == 1)
            paper_remaining = sum(1 for unit in units if unit.unit_type == 2)
            
            counts = [scissors_remaining, rock_remaining, paper_remaining]
            winner_index = counts.index(max(counts))
            winner_name = ["Scissors", "Rock", "Paper"][winner_index]
            
            print(f"Time limit reached! {winner_name} has the most units ({counts[winner_index]})!")
            status_message = f"Time Limit! {winner_name} leads with {counts[winner_index]} units"
            running = False
            
        # Check end condition
        if check_end_condition(units):
            if units:
                winner_type = units[0].unit_type
                winner_name = ["Scissors", "Rock", "Paper"][winner_type]
                print(f"Simulation ended! {winner_name} wins!")
                status_message = f"Game Over! {winner_name} wins!"
            else:
                print("Simulation ended with no units left!")
                status_message = "Game Over! No units left!"
            running = False
        
        # Draw everything
        screen.fill(BACKGROUND_COLOR)
        
        # Display counts and status
        type_counts = np.bincount([unit.unit_type for unit in units], minlength=3)
        scissors_remaining, rock_remaining, paper_remaining = type_counts
        
        font = pygame.font.SysFont(None, 24)
        
        # Count text
        count_text = f"Scissors: {scissors_remaining} | Rock: {rock_remaining} | Paper: {paper_remaining}"
        text = font.render(count_text, True, (255, 255, 255))
        screen.blit(text, (10, 10))
        
        # Status message
        status_text = font.render(status_message, True, (255, 255, 0))
        screen.blit(status_text, (WIDTH // 2 - status_text.get_width() // 2, 10))
        
        # Calculate frame time and FPS
        frame_time = time.time() - start_time
        frame_count += 1
        if time.time() - fps_timer > 1.0:  # Update FPS every second
            current_fps = frame_count / (time.time() - fps_timer)
            fps_timer = time.time()
            frame_count = 0
        else:
            current_fps = clock.get_fps()
            
        # Time steps and performance info
        perf_text = f"Time: {time_steps}/{MAX_TIME} | FPS: {int(current_fps)} | Frame: {frame_time*1000:.1f}ms"
        time_text = font.render(perf_text, True, (200, 200, 200))
        screen.blit(time_text, (WIDTH - 450, 10))
        
        # Detailed performance breakdown
        breakdown_text = f"Tree: {tree_time*1000:.1f}ms | Target: {target_time*1000:.1f}ms | Move: {move_time*1000:.1f}ms"
        breakdown_render = font.render(breakdown_text, True, (150, 150, 150))
        screen.blit(breakdown_render, (WIDTH - 450, 35))
        
        for unit in units:
            unit.draw()
        
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()

if __name__ == "__main__":
    main()
