# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
# cython: initializedcheck=False, nonecheck=False

import numpy as np
cimport numpy as np
from libc.math cimport sqrt, hypot, cos, sin, M_PI
from libc.stdlib cimport rand, RAND_MAX

# Define constants
cdef double MIN_DISTANCE = 10.0  # UNIT_RADIUS * 2
cdef double REPULSION_FACTOR = 4.0
cdef double REPULSION_RADIUS = 150.0
cdef double UNIT_SPEED = 2.0
cdef double RANDOM_MOVEMENT = 0.5
cdef double COLLISION_CHANCE = 0.3
cdef double GROUP_SEPARATION = 0.82
cdef double GROUP_MIN_DISTANCE = 30.0
cdef double GROUP_COHESION = 0.1
cdef double GROUP_ALIGNMENT = 0.1
cdef double GROUP_RADIUS = 100.0
cdef double CENTER_FORCE = 0.9
cdef int WIDTH = 960
cdef int HEIGHT = 960

# Type definitions
ctypedef struct UnitStruct:
    int unit_type
    double x
    double y
    double vx
    double vy
    int target_index

# Helper functions
cdef double rand_double() nogil:
    cdef double r = rand() / (RAND_MAX + 1.0)
    return r

cdef double distance(double x1, double y1, double x2, double y2) nogil:
    return hypot(x2 - x1, y2 - y1)

cdef int is_inside_unit(double x, double y, double ux, double uy, double radius) nogil:
    cdef double dist = distance(x, y, ux, uy)
    return 1 if dist < radius else 0

cdef int find_target(int unit_type, double unit_x, double unit_y, 
                    double[:, :] positions, int[:] types, int unit_count) nogil:
    """Find nearest target unit that this unit can chase"""
    cdef int target_type = (unit_type + 2) % 3
    cdef double min_dist = 1e9
    cdef int target_index = -1
    cdef double d
    cdef int i
    
    # Find the closest target
    for i in range(unit_count):
        if types[i] == target_type:
            d = distance(unit_x, unit_y, positions[i, 0], positions[i, 1])
            if d < min_dist:
                min_dist = d
                target_index = i
    
    return target_index

cdef void calculate_movement(int unit_index, double[:, :] positions, int[:] types, 
                           double[:, :] velocities, int[:] targets, int unit_count) nogil:
    """Calculate movement for a single unit"""
    cdef double unit_x = positions[unit_index, 0]
    cdef double unit_y = positions[unit_index, 1]
    cdef int unit_type = types[unit_index]
    
    # Initialize velocity components
    cdef double vx = 0.0
    cdef double vy = 0.0
    
    # Get target information
    cdef int target_index = targets[unit_index]
    cdef double dx, dy, dist, strength
    
    # Attraction to target
    if target_index >= 0:
        dx = positions[target_index, 0] - unit_x
        dy = positions[target_index, 1] - unit_y
        dist = hypot(dx, dy)
        
        if dist > 0:
            # Attraction force
            strength = max(0.7, 1 - REPULSION_FACTOR/2)
            vx = (dx / dist) * UNIT_SPEED * strength
            vy = (dy / dist) * UNIT_SPEED * strength
    
    # Repulsion from threats (units that can defeat this unit)
    cdef int predator_type = (unit_type + 1) % 3
    cdef int i
    
    for i in range(unit_count):
        if i != unit_index and types[i] == predator_type:
            dx = unit_x - positions[i, 0]
            dy = unit_y - positions[i, 1]
            dist = hypot(dx, dy)
            
            if 0 < dist < REPULSION_RADIUS:
                # Repulsion force
                strength = REPULSION_FACTOR * (1 - dist / REPULSION_RADIUS)
                vx += (dx / dist) * strength
                vy += (dy / dist) * strength
    
    # Group behavior with same type units
    cdef double sep_x = 0.0
    cdef double sep_y = 0.0
    cdef int sep_count = 0
    cdef double center_x = 0.0
    cdef double center_y = 0.0
    cdef int group_count = 0
    cdef double avg_vx = 0.0
    cdef double avg_vy = 0.0
    
    for i in range(unit_count):
        if i != unit_index and types[i] == unit_type:
            dx = unit_x - positions[i, 0]
            dy = unit_y - positions[i, 1]
            dist = hypot(dx, dy)
            
            if dist < GROUP_RADIUS:
                # Count this unit for group calculations
                group_count += 1
                
                # Separation - avoid crowding neighbors
                if dist < GROUP_MIN_DISTANCE and dist > 0:
                    strength = 1.0 - (dist / GROUP_MIN_DISTANCE)
                    sep_x += (dx / dist) * strength
                    sep_y += (dy / dist) * strength
                    sep_count += 1
                
                # Add to center of mass calculation
                center_x += positions[i, 0]
                center_y += positions[i, 1]
                
                # Add to velocity alignment
                avg_vx += velocities[i, 0]
                avg_vy += velocities[i, 1]
    
    # Apply separation if any neighbors are too close
    if sep_count > 0:
        vx += sep_x * GROUP_SEPARATION
        vy += sep_y * GROUP_SEPARATION
    
    # Apply cohesion if there are group members
    if group_count > 0:
        center_x /= group_count
        center_y /= group_count
        
        # Only apply cohesion if not too close to center of mass
        dx = center_x - unit_x
        dy = center_y - unit_y
        dist = hypot(dx, dy)
        
        if dist > GROUP_MIN_DISTANCE:
            vx += (dx / dist) * GROUP_COHESION
            vy += (dy / dist) * GROUP_COHESION
        
        # Apply alignment
        avg_vx /= group_count
        avg_vy /= group_count
        vx += avg_vx * GROUP_ALIGNMENT
        vy += avg_vy * GROUP_ALIGNMENT
    
    # Center attraction to prevent edge clustering
    dx = WIDTH / 2 - unit_x
    dy = HEIGHT / 2 - unit_y
    dist = hypot(dx, dy)
    
    if dist > WIDTH / 4:  # Only apply when far from center
        strength = CENTER_FORCE * (dist / (WIDTH/2))
        if dist > 0:
            vx += (dx / dist) * strength
            vy += (dy / dist) * strength
    
    # Add random movement
    vx += (rand_double() - 0.5) * RANDOM_MOVEMENT
    vy += (rand_double() - 0.5) * RANDOM_MOVEMENT
    
    # --- Global separation: force all units to avoid overlapping ---
    cdef double strong_sep_x = 0.0
    cdef double strong_sep_y = 0.0
    cdef double force
    
    for i in range(unit_count):
        if i != unit_index:
            dx = unit_x - positions[i, 0]
            dy = unit_y - positions[i, 1]
            dist = hypot(dx, dy)
            
            if dist < MIN_DISTANCE/1.05 and dist > 0:
                # Strong separation force
                force = 20.0 * (MIN_DISTANCE - dist) / MIN_DISTANCE
                strong_sep_x += (dx / dist) * force
                strong_sep_y += (dy / dist) * force
    
    vx += strong_sep_x
    vy += strong_sep_y
    
    # Normalize velocity if too high
    cdef double speed = hypot(vx, vy)
    if speed > UNIT_SPEED:
        vx = (vx / speed) * UNIT_SPEED
        vy = (vy / speed) * UNIT_SPEED
    
    # Store the calculated velocity
    velocities[unit_index, 0] = vx
    velocities[unit_index, 1] = vy

cdef void apply_movement(int unit_count, double[:, :] positions, double[:, :] velocities) nogil:
    """Apply calculated velocities to positions and handle boundaries"""
    cdef int i
    cdef double x, y, vx, vy
    
    for i in range(unit_count):
        # Get current position and velocity
        x = positions[i, 0]
        y = positions[i, 1]
        vx = velocities[i, 0]
        vy = velocities[i, 1]
        
        # Apply movement
        x += vx
        y += vy
        
        # Boundary handling with bounce
        if x < 5:  # UNIT_RADIUS
            x = 5
            vx *= -0.5  # Bounce with energy loss
        elif x > WIDTH - 5:
            x = WIDTH - 5
            vx *= -0.5
            
        if y < 5:
            y = 5
            vy *= -0.5
        elif y > HEIGHT - 5:
            y = HEIGHT - 5
            vy *= -0.5
        
        # Update position and velocity
        positions[i, 0] = x
        positions[i, 1] = y
        velocities[i, 0] = vx
        velocities[i, 1] = vy

cdef void check_collisions(int unit_count, double[:, :] positions, int[:] types, int[:] new_types) nogil:
    """Check for collisions between units and update types"""
    cdef int i, j
    cdef int predator_type
    cdef double dist
    
    for i in range(unit_count):
        if new_types[i] < 0:  # Only check if not already changed
            predator_type = (types[i] + 1) % 3
            
            for j in range(unit_count):
                if i != j and types[j] == predator_type:
                    dist = distance(positions[i, 0], positions[i, 1], 
                                   positions[j, 0], positions[j, 1])
                    
                    if dist < MIN_DISTANCE:
                        # Collision occurred, check if type should change
                        if rand_double() < COLLISION_CHANCE:
                            new_types[i] = predator_type
                            break

# Python-accessible functions
def find_all_targets(np.ndarray[double, ndim=2] positions, np.ndarray[int, ndim=1] types):
    """Find targets for all units"""
    cdef int unit_count = positions.shape[0]
    cdef np.ndarray[int, ndim=1] targets = np.full(unit_count, -1, dtype=np.int32)
    cdef int i
    
    for i in range(unit_count):
        targets[i] = find_target(types[i], positions[i, 0], positions[i, 1],
                               positions, types, unit_count)
    
    return targets

def update_movement(np.ndarray[double, ndim=2] positions, 
                   np.ndarray[int, ndim=1] types,
                   np.ndarray[int, ndim=1] targets):
    """Update positions for all units"""
    cdef int unit_count = positions.shape[0]
    cdef np.ndarray[double, ndim=2] velocities = np.zeros((unit_count, 2), dtype=np.float64)
    cdef int i
    
    # Calculate movements for all units
    for i in range(unit_count):
        calculate_movement(i, positions, types, velocities, targets, unit_count)
    
    # Apply movements to all units
    apply_movement(unit_count, positions, velocities)
    
    return velocities

def check_all_collisions(np.ndarray[double, ndim=2] positions, np.ndarray[int, ndim=1] types):
    """Check collisions for all units and return new types"""
    cdef int unit_count = positions.shape[0]
    cdef np.ndarray[int, ndim=1] new_types = np.full(unit_count, -1, dtype=np.int32)
    
    check_collisions(unit_count, positions, types, new_types)
    
    return new_types

def initialize_random_positions(int count, int width, int height, int radius):
    """Generate random positions for units"""
    cdef np.ndarray[double, ndim=2] positions = np.zeros((count, 2), dtype=np.float64)
    cdef int i
    
    for i in range(count):
        positions[i, 0] = radius + rand_double() * (width - 2 * radius)
        positions[i, 1] = radius + rand_double() * (height - 2 * radius)
    
    return positions
