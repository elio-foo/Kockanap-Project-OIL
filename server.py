"""
Flask API Server for Firefighting AI
====================================
Provides HTTP endpoints to interface with MainProgram.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os

# Add the OpenRA directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from OpenRA.MainProgram import Fire, FireFighter, Truck, Drone, astar

app = Flask(__name__)
CORS(app)

# --- Game State ---
GRID_SIZE = (40, 40)
fires = []
units = []
water_sources = []

def init_state():
    """Initialize default fires and units"""
    import random
    global fires, units, water_sources
    
    fires = [
        Fire((random.randint(0, 39), random.randint(0, 39)), random.randint(100, 400))
        for _ in range(6)
    ]
    
    units = [
        FireFighter((0, 0)),
        Truck((10, 10)),
        Drone((30, 30)),
    ]
    
    # Random water sources (5-8 sources)
    water_sources = [
        (random.randint(0, 39), random.randint(0, 39))
        for _ in range(random.randint(5, 8))
    ]

init_state()

# --- API Endpoints ---

@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current simulation state"""
    return jsonify({
        'fires': [{'x': f.position[0], 'y': f.position[1], 'intensity': f.intensity} for f in fires],
        'units': [
            {
                'name': u.name,
                'x': u.position[0],
                'y': u.position[1],
                'hp': u.hp,
                'max_hp': u.max_hp,
                'water': u.water,
                'max_water': u.max_water,
                'damage': u.damage,
                'sight': u.sight,
                'speed': u.speed,
                'path': [{'x': p[0], 'y': p[1]} for p in u.path] if hasattr(u, 'path') else [],
                'target': {'x': u.target.position[0], 'y': u.target.position[1]} if u.target else None
            } for u in units
        ],
        'water_sources': [{'x': w[0], 'y': w[1]} for w in water_sources],
        'grid_size': GRID_SIZE
    })

@app.route('/api/step', methods=['POST'])
def step_simulation():
    """Run one simulation step"""
    global fires, units
    
    # Each unit acts
    for unit in units:
        if not fires:
            continue
        
        # Check if unit needs water refill - go to nearest water source
        if unit.needs_refill():
            nearest_water = min(water_sources, key=lambda w: unit.distance(unit.position, w))
            if unit.distance(unit.position, nearest_water) <= 1:
                # At water source - refill
                unit.water = unit.max_water
            else:
                # Move toward water source
                path = astar(unit.position, nearest_water, GRID_SIZE)
                if path:
                    unit.path = path
                    unit.move()
            # Skip fire fighting if needs water
            continue
            
        # Choose target
        target = unit.choose_target(fires, units, set())
        
        if target:
            # Check if within 2 blocks (extinguish range)
            dist = unit.distance(unit.position, target.position)
            
            if dist <= 2:
                # Extinguish fire
                unit.fight_fire(target)
            else:
                # Move toward target using A*
                path = astar(unit.position, target.position, GRID_SIZE)
                if path:
                    unit.path = path
                    unit.move()
    
    # Remove extinguished fires
    fires = [f for f in fires if f.intensity > 0]
    
    # Fire spreads randomly
    new_fires = []
    for fire in fires:
        if fire.intensity > 50 and random.random() < 0.15:  # 15% chance to spread
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            new_pos = (fire.position[0] + dx, fire.position[1] + dy)
            
            # Check bounds
            if 0 <= new_pos[0] < GRID_SIZE[0] and 0 <= new_pos[1] < GRID_SIZE[1]:
                # Check if fire already exists at position
                if not any(f.position == new_pos for f in fires):
                    new_fires.append(Fire(new_pos, fire.intensity // 2))
    
    fires.extend(new_fires)
    
    return jsonify({
        'fires': [{'x': f.position[0], 'y': f.position[1], 'intensity': f.intensity} for f in fires],
        'units': [
            {
                'name': u.name,
                'x': u.position[0],
                'y': u.position[1],
                'hp': u.hp,
                'max_hp': u.max_hp,
                'water': u.water,
                'max_water': u.max_water,
                'damage': u.damage,
                'sight': u.sight,
                'speed': u.speed,
                'path': [{'x': p[0], 'y': p[1]} for p in u.path] if hasattr(u, 'path') else [],
                'target': {'x': u.target.position[0], 'y': u.target.position[1]} if u.target else None
            } for u in units
        ],
        'water_sources': [{'x': w[0], 'y': w[1]} for w in water_sources]
    })

@app.route('/api/add_fire', methods=['POST'])
def add_fire():
    """Add a new fire at random or specified position"""
    import random
    data = request.json or {}
    
    x = data.get('x', random.randint(0, 39))
    y = data.get('y', random.randint(0, 39))
    intensity = data.get('intensity', random.randint(100, 400))
    
    fires.append(Fire((x, y), intensity))
    
    return jsonify({'success': True, 'fire': {'x': x, 'y': y, 'intensity': intensity}})

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset simulation to initial state"""
    init_state()
    return jsonify({'success': True})

@app.route('/api/add_water', methods=['POST'])
def add_water():
    """Add a water source at random or specified position"""
    import random
    data = request.json or {}
    
    x = data.get('x', random.randint(0, 39))
    y = data.get('y', random.randint(0, 39))
    
    if (x, y) not in water_sources:
        water_sources.append((x, y))
    
    return jsonify({'success': True, 'water_sources': [{'x': w[0], 'y': w[1]} for w in water_sources]})

@app.route('/api/unit/<name>/refill', methods=['POST'])
def refill_unit(name):
    """Refill a unit's water"""
    for unit in units:
        if unit.name == name:
            unit.water = unit.max_water
            return jsonify({'success': True, 'unit': unit.name, 'water': unit.water})
    return jsonify({'success': False, 'error': 'Unit not found'}), 404

if __name__ == '__main__':
    print("🔥 Firefighting AI Server running on http://localhost:5000")
    app.run(debug=True, port=5000)