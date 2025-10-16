import socket
import threading

HOST = '127.0.0.1'
PORT = 12345

clients = []
clients_lock = threading.Lock()
games = {}
players = {}
player_connections = {}


def send_message(client, message):
    try:
        client.sendall((message + '\n').encode('utf-8'))
    except (ConnectionResetError, BrokenPipeError):
        print(f"[ОШИБКА] Не удалось отправить сообщение клиенту {client}")


def create_board():
    return [[" " for _ in range(3)] for _ in range(3)]


def board_to_string(board):
    positions = []
    for i in range(3):
        for j in range(3):
            if board[i][j] != " ":
                row_char = chr(65+i)
                col_num = j + 1
                positions.append(f"{row_char}{col_num}:{board[i][j]}")
    return ",".join(positions)


def check_winner(board):
    for i in range(3):
        if board[i][0] == board[i][1] == board[i][2] != " ":
            return board[i][0]
    for j in range(3):
        if board[0][j] == board[1][j] == board[2][j] != " ":
            return board[0][j]
    if board[0][0] == board[1][1] == board[2][2] != " ":
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != " ":
        return board[0][2]
    return None


def check_draw(board):
    return all(ceil != " " for row in board for ceil in row)


def find_opponent(player_name):
    for name, data in games.items():
        if data["opponent"] is None and name != player_name:
            return name
    return None


def handle_client(conn, addr):
    print(f"[НОВОЕ ПОДКЛЮЧЕНИЕ] {addr}")
    with clients_lock:
        clients.append(conn)

    player_name = f"Player{addr[1]}"
    players[conn] = player_name
    player_connections[player_name] = conn

    try:
        opponent_name = find_opponent(player_name)
        if opponent_name:
            game_data = games[opponent_name]
            game_data["opponent"] = player_name
            game_data["player2"] = player_name
            game_data["symbol2"] = "O"
            games[player_name] = game_data

            send_message(conn, f"OPPONENT {opponent_name}")
            send_message(conn, f"BOARD {board_to_string(game_data['board'])}")
            send_message(conn, f"TURN {game_data['turn']}")
            send_message(conn, f"SYMBOL O")

            if opponent_name in player_connections:
                send_message(player_connections[opponent_name], f"OPPONENT {player_name}")
        else:
            games[player_name] = {
                "opponent": None,
                "player1": player_name,
                "board": create_board(),
                "turn": "X",
                "symbol1": "X",
                "game_over": False
            }
            send_message(conn, "WAITING ожидаем подключение соперника")

        while True:
            data = conn.recv(1024).decode('utf-8').strip()
            if not data:
                break

            if data.startswith("MOVE"):
                parts = data.split()
                if len(parts) >= 2:
                    move = parts[1].upper()
                    process_move(conn, player_name, move)
                else:
                    send_message(conn, "ERROR неверная команда MOVE")
            elif data.lower().startswith("chat "):
                message = data[5:]
                broadcast_chat_message(player_name, message)
            elif data.startswith("STATUS"):
                send_status(conn, player_name)
            elif data.lower() == "exit":
                break
            else:
                send_message(conn, "ERROR неизвестная команда")

    except ConnectionResetError:
        print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} отключился")
    finally:
        cleanup_player(conn, player_name)
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        players.pop(conn, None)
        player_connections.pop(player_name, None)
        conn.close()


def process_move(conn, player_name, move):
    if player_name not in games:
        send_message(conn, "ERROR нет активной игры")
        return

    game_data = games[player_name]

    if game_data.get("game_over", False):
        send_message(conn, "ERROR игра уже завершена")
        return

    if game_data["opponent"] is None:
        send_message(conn, "ERROR нет соперника")
        return

    board = game_data["board"]
    current_turn = game_data["turn"]

    if player_name == game_data["player1"]:
        player_symbol = game_data["symbol1"]
    else:
        player_symbol = game_data["symbol2"]

    if player_symbol != current_turn:
        send_message(conn, "ERROR сейчас не твой ход")
        return

    if len(move) != 2 or not move[0].isalpha() or not move[1].isdigit():
        send_message(conn, "ERROR неверный формат")
        return

    row = ord(move[0].upper()) - 65
    col = int(move[1]) - 1

    if not (0 <= row <= 2 and 0 <= col <= 2):
        send_message(conn, "ERROR клетка вне поля")
        return

    if board[row][col] != " ":
        send_message(conn, "ERROR клетка занята")
        return

    board[row][col] = player_symbol

    winner = check_winner(board)
    if winner:
        game_data["game_over"] = True
        broadcast_to_game(player_name, f"BOARD {board_to_string(board)}")
        winner_name = game_data["player1"] if winner == "X" else game_data["player2"]
        broadcast_to_game(player_name, f"WIN {winner_name} выиграл! ИГРА ЗАВЕРШЕНА")
        return

    if check_draw(board):
        game_data["game_over"] = True
        broadcast_to_game(player_name, f"BOARD {board_to_string(board)}")
        broadcast_to_game(player_name, "DRAW Ничья! ИГРА ЗАВЕРШЕНА")
        return

    # Переход хода
    game_data["turn"] = "O" if current_turn == "X" else "X"
    broadcast_to_game(player_name, f"BOARD {board_to_string(board)}")
    broadcast_to_game(player_name, f"TURN {game_data['turn']}")


def broadcast_chat_message(player_name, message):
    if player_name not in games:
        return
    game_data = games[player_name]
    for name in [game_data.get("player1"), game_data.get("player2")]:
        if name and name in player_connections:
            send_message(player_connections[name], f"CHAT {player_name}:{message}")


def send_status(conn, player_name):
    if player_name not in games:
        send_message(conn, "ERROR нет активной игры")
        return
    game_data = games[player_name]
    send_message(conn, f"TURN {game_data['turn']}")
    if game_data.get("opponent"):
        send_message(conn, f"OPPONENT {game_data['opponent']}")
    send_message(conn, "STATUS OK")  


def broadcast_to_game(player_name, message):
    game_data = games.get(player_name)
    if not game_data:
        return
    for name in [game_data.get("player1"), game_data.get("player2")]:
        if name and name in player_connections:
            send_message(player_connections[name], message)


def cleanup_player(conn, player_name):
    if player_name in games:
        game_data = games[player_name]
        opponent = game_data.get("opponent")
        if opponent and opponent in player_connections:
            send_message(player_connections[opponent], "OPPONENT_DISCONNECTED соперник отключился")
        games.pop(player_name, None)


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[SERVER RUNNING] {HOST}:{PORT}")
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()
