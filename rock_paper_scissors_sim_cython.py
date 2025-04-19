import pygame
import numpy as np
import random
import sys
import math
import time
from shapely.geometry import Point, Polygon

# Import our Cython-optimized core
import rock_paper_scissors_core as core

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 960, 960
FPS = 144

# Benchmark support
if len(sys.argv) >= 5 and sys.argv[4] == '-b':
    MAX_TIME = int(sys.argv[5])
    print(f'Running in benchmark mode with MAX_TIME={MAX_TIME}')

MAX_TIME = 30000  # frames before declaring a draw
BACKGROUND_COLOR = (30, 30, 30)

# Obstacle settings
NUM_OBSTACLES = 5
OBSTACLE_COLOR = (80, 80, 80)

# Visual settings
UNIT_RADIUS = 5
SCISSORS_COLOR = (255, 0, 0)      # Red
ROCK_COLOR = (100, 100, 100)      # Gray
PAPER_COLOR = (0, 0, 255)         # Blue
SHOW_ATTRACTIONS = False          # Whether to show attraction/repulsion lines

# Initialize screen
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rock Paper Scissors Simulation (Cython)")
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

class CythonSimulation:
    def __init__(self, scissors_count, rock_count, paper_count):
        self.total_count = scissors_count + rock_count + paper_count
        
        # Initialize positions
        self.positions = np.zeros((self.total_count, 2), dtype=np.float64)
        
        # Initialize unit types (0: Scissors, 1: Rock, 2: Paper)
        self.types = np.zeros(self.total_count, dtype=np.int32)
        
        # Set initial positions and types
        self.initialize_units(scissors_count, rock_count, paper_count)
        
        # Initialize targets array
        self.targets = np.full(self.total_count, -1, dtype=np.int32)
        
        # Initialize velocities
        self.velocities = np.zeros((self.total_count, 2), dtype=np.float64)

    def initialize_units(self, scissors_count, rock_count, paper_count):
        """Initialize unit positions and types"""
        # Generate all positions at once
        self.positions = core.initialize_random_positions(self.total_count, WIDTH, HEIGHT, UNIT_RADIUS)
        
        # Set types
        idx = 0
        
        # Scissors (type 0)
        for i in range(scissors_count):
            self.types[idx] = 0
            idx += 1
        
        # Rock (type 1)
        for i in range(rock_count):
            self.types[idx] = 1
            idx += 1
        
        # Paper (type 2)
        for i in range(paper_count):
            self.types[idx] = 2
            idx += 1

    def update(self):
        """Update simulation state for one frame"""
        # Update targets
        self.targets = core.find_all_targets(self.positions, self.types)
        
        # Update movement
        self.velocities = core.update_movement(self.positions, self.types, self.targets)
        
        # Check collisions
        new_types = core.check_all_collisions(self.positions, self.types)
        
        # Apply new types
        for i in range(self.total_count):
            if new_types[i] >= 0:
                self.types[i] = new_types[i]
    
    def draw(self):
        """Draw all units to the screen"""
        # Draw units
        for i in range(self.total_count):
            x, y = int(self.positions[i, 0]), int(self.positions[i, 1])
            
            # Set color based on type
            if self.types[i] == 0:  # Scissors
                color = SCISSORS_COLOR
            elif self.types[i] == 1:  # Rock
                color = ROCK_COLOR
            else:  # Paper
                color = PAPER_COLOR
            
            # Draw unit
            pygame.draw.circle(screen, color, (x, y), UNIT_RADIUS)
            
            # Draw attraction line to target
            if SHOW_ATTRACTIONS and self.targets[i] >= 0:
                # Draw a line to target (prey) - green line
                target_x = int(self.positions[self.targets[i], 0])
                target_y = int(self.positions[self.targets[i], 1])
                pygame.draw.line(screen, (0, 200, 0), (x, y), (target_x, target_y), 1)
    
    def check_end_condition(self):
        """Check if simulation has ended (all units same type)"""
        if self.total_count == 0:
            return True
        
        # Check if all units are the same type
        first_type = self.types[0]
        return np.all(self.types == first_type)
        
    def get_type_counts(self):
        """Get counts of each unit type"""
        unique, counts = np.unique(self.types, return_counts=True)
        counts_dict = dict(zip(unique, counts))
        
        # Ensure all types have counts (even if zero)
        scissors_count = counts_dict.get(0, 0)
        rock_count = counts_dict.get(1, 0)
        paper_count = counts_dict.get(2, 0)
        
        return scissors_count, rock_count, paper_count

def main():
    # Get initial counts from command line arguments or use defaults
    scissors_count = 200
    rock_count = 200
    paper_count = 200

    if len(sys.argv) >= 4:
        scissors_count = int(sys.argv[1])
        rock_count = int(sys.argv[2])
        paper_count = int(sys.argv[3])

    # Initialize simulation
    simulation = CythonSimulation(scissors_count, rock_count, paper_count)
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
        
        # Start performance timer for simulation update
        update_start_time = time.time()
        
        # Update simulation
        simulation.update()
        
        update_time = time.time() - update_start_time
        
        # Time limit check
        time_steps += 1
        if time_steps >= MAX_TIME:
            # Determine which type has the most units
            scissors_remaining, rock_remaining, paper_remaining = simulation.get_type_counts()
            
            counts = [scissors_remaining, rock_remaining, paper_remaining]
            winner_index = counts.index(max(counts))
            winner_name = ["Scissors", "Rock", "Paper"][winner_index]
            
            print(f"Time limit reached! {winner_name} has the most units ({counts[winner_index]})!")
            status_message = f"Time Limit! {winner_name} leads with {counts[winner_index]} units"
            running = False
            
        # Check end condition
        if simulation.check_end_condition():
            scissors_remaining, rock_remaining, paper_remaining = simulation.get_type_counts()
            if sum([scissors_remaining, rock_remaining, paper_remaining]) > 0:
                # Find winner type
                if scissors_remaining > 0:
                    winner_type = 0
                elif rock_remaining > 0:
                    winner_type = 1
                else:
                    winner_type = 2
                    
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
        scissors_remaining, rock_remaining, paper_remaining = simulation.get_type_counts()
        
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
        breakdown_text = f"Update: {update_time*1000:.1f}ms"
        breakdown_render = font.render(breakdown_text, True, (150, 150, 150))
        screen.blit(breakdown_render, (WIDTH - 450, 35))
        
        # Draw all units
        simulation.draw()
        
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()

if __name__ == "__main__":
    main()
