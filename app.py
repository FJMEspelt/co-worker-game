from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, emit
import uuid
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure random key
socketio = SocketIO(app)

# Global variables to store game state
players = {}  # key = session_id, value = {'username': ..., 'phrase': ..., 'score': 0}
game_state = 'waiting'  # 'waiting', 'round', or 'ended'
rounds = []  # each round: {'phrase': ..., 'author': ..., 'candidates': [...], 'votes': {}}
current_round_index = -1

def get_current_round():
    if 0 <= current_round_index < len(rounds):
        return rounds[current_round_index]
    return None

def all_votes_in():
    current_round = get_current_round()
    if not current_round:
        return False
    return len(current_round['votes']) >= len(players)

@app.route('/', methods=['GET', 'POST'])
def index():
    global players
    if request.method == 'POST':
        username = request.form.get('username')
        phrase = request.form.get('phrase')
        if not username or not phrase:
            return render_template('index.html', error="Please enter both username and phrase.")
        if 'player_id' not in session:
            session['player_id'] = str(uuid.uuid4())
        player_id = session['player_id']
        if player_id not in players:
            players[player_id] = {'username': username, 'phrase': phrase, 'score': 0}
            # Notify everyone that a new player has joined.
            socketio.emit('update', {'message': 'New player joined'})
        return redirect(url_for('waiting'))
    return render_template('index.html')

@app.route('/waiting')
def waiting():
    return render_template('waiting.html', players=players, game_state=game_state, current_user=players.get(session.get('player_id')))

@app.route('/start', methods=['POST'])
def start_game():
    global game_state, rounds, current_round_index
    player_id = session.get('player_id')
    if not player_id or players.get(player_id, {}).get('username') != "Javier Molina":
        return redirect(url_for('waiting'))
    rounds = []
    for p in players.values():
        rounds.append({'phrase': p['phrase'], 'author': p['username'], 'candidates': [], 'votes': {}})
    random.shuffle(rounds)
    for rnd in rounds:
        candidate_usernames = [rnd['author']]
        other_players = [p['username'] for p in players.values() if p['username'] != rnd['author']]
        random.shuffle(other_players)
        candidate_usernames += other_players[:5]  # up to 5 others
        random.shuffle(candidate_usernames)
        rnd['candidates'] = candidate_usernames
    current_round_index = 0
    game_state = 'round'
    socketio.emit('update', {'message': 'Game started'})
    return redirect(url_for('round_view'))

@app.route('/round', methods=['GET'])
def round_view():
    if game_state != 'round':
        return redirect(url_for('waiting'))
    current_round = get_current_round()
    if not current_round:
        return redirect(url_for('results'))
    player_id = session.get('player_id')
    current_vote = current_round['votes'].get(player_id)
    return render_template('round.html',
                           round=current_round,
                           current_round_index=current_round_index+1,
                           total_rounds=len(rounds),
                           vote=current_vote,
                           all_votes=all_votes_in(),
                           players=players,
                           current_user=players.get(player_id))

@app.route('/vote', methods=['POST'])
def vote():
    player_id = session.get('player_id')
    if not player_id:
        return redirect(url_for('index'))
    choice = request.form.get('choice')
    current_round = get_current_round()
    if not current_round:
        return redirect(url_for('waiting'))
    if player_id in current_round['votes']:
        return redirect(url_for('round_view'))
    current_round['votes'][player_id] = choice
    if choice == current_round['author']:
        players[player_id]['score'] += 1
    socketio.emit('update', {'message': 'Vote cast'})
    return redirect(url_for('round_view'))

@app.route('/next_round', methods=['POST'])
def next_round():
    global current_round_index, game_state
    player_id = session.get('player_id')
    if not player_id or players.get(player_id, {}).get('username') != "Javier Molina":
        return redirect(url_for('round_view'))
    if current_round_index < len(rounds) - 1:
        current_round_index += 1
        socketio.emit('update', {'message': 'Next round started'})
        return redirect(url_for('round_view'))
    else:
        game_state = 'ended'
        socketio.emit('update', {'message': 'Game ended'})
        return redirect(url_for('results'))

@app.route('/results')
def results():
    sorted_players = sorted(players.values(), key=lambda p: p['score'], reverse=True)
    podium = sorted_players[:3]
    return render_template('results.html', podium=podium, players=players)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
