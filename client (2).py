import socket
import threading
import re
import time
import select

HOST = '127.0.0.1'
PORT = 12345

class GameClient:
    def __init__(self):
        self.socket = None
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.current_turn = "X"
        self.opponent = None
        self.game_active = True
        self.my_symbol = None
        self.buffer = ""
        self.pending_messages = []  
        self.need_display = False   
        self.last_displayed_state = ""  
    
    def display_board(self):
        current_board_state = str(self.board) + str(self.current_turn) + str(self.game_active) + str(self.opponent)
        if self.last_displayed_state == current_board_state and not self.need_display:
            return
            
        print("\n" + "="*50)
        print("          КРЕСТИКИ-НОЛИКИ")
        print("="*50)
        print("    1   2   3")
        print("  ┌───┬───┬───┐")
        for i in range(3):
            row_char = chr(65 + i)  
            print(f"{row_char} │ {self.board[i][0]} │ {self.board[i][1]} │ {self.board[i][2]} │")
            if i < 2:
                print("  ├───┼───┼───┤")
        print("  └───┴───┴───┘")

        if self.game_active:
            if not self.my_symbol:
                print(f"Ход: {self.current_turn}")
            elif self.current_turn == self.my_symbol:
                print("Ваш ход!")
            else:
                print("Ход соперника.")
        else:
            print("ИГРА ЗАВЕРШЕНА - можно общаться в чате")
        
        if self.opponent:
            print(f"Соперник: {self.opponent}")
        print("="*50)
        
        self.last_displayed_state = current_board_state
        self.need_display = False

    def update_board(self, board_str):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        
        if board_str and board_str != "WAITING":
            positions = board_str.split(',')
            for pos in positions:
                if ':' in pos:
                    coord, player = pos.split(':')
                    if len(coord) >= 2:
                        row = ord(coord[0].upper()) - 65
                        col = int(coord[1]) - 1
                        if 0 <= row <= 2 and 0 <= col <= 2:
                            self.board[row][col] = player

    def receive_messages(self):
        while True:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    print("\n[ОТКЛЮЧЕНИЕ] Сервер закрыл соединение")
                    break

                self.buffer += data
                
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        self.pending_messages.append(line)

                timeout = 0.05
                while True:
                    rlist, _, _ = select.select([self.socket], [], [], timeout)
                    if rlist:
                        extra = self.socket.recv(4096).decode('utf-8')
                        if not extra:
                            print("\n[ОТКЛЮЧЕНИЕ] Сервер закрыл соединение")
                            return
                        self.buffer += extra
                        while '\n' in self.buffer:
                            line, self.buffer = self.buffer.split('\n', 1)
                            line = line.strip()
                            if line:
                                self.pending_messages.append(line)
                        
                        timeout = 0.01
                        continue
                    break

                
                if self.pending_messages:
                    self.process_all_messages()
                    self.show_prompt()
                        
            except ConnectionResetError:
                print("\n[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером")
                break
            except Exception as e:
                print(f"\n[ОШИБКА] Ошибка приема сообщений: {e}")
                break

    def process_all_messages(self):
        game_state_changed = False

        while self.pending_messages:
            message = self.pending_messages.pop(0)
            
            if message.startswith("BOARD"):
                board_data = message[6:]  
                self.update_board(board_data)
                game_state_changed = True
            elif message.startswith("TURN"):
                self.current_turn = message[5:]
                game_state_changed = True
            elif message.startswith("CHAT"):
                chat_message = message[5:]  
                print(f"\n[ЧАТ] {chat_message}")
            elif message.startswith("WIN"):
                win_message = message[4:]
                self.game_active = False
                print(f"\n {win_message} ")
                game_state_changed = True
                print("\nТеперь можно общаться в чате. Команды: 'chat сообщение' или 'exit'")
            elif message.startswith("DRAW"):
                draw_message = message[5:]
                self.game_active = False
                print(f"\n {draw_message} ")
                game_state_changed = True
                print("\nТеперь можно общаться в чате. Команды: 'chat сообщение' или 'exit'")
            elif message.startswith("OPPONENT"):
                self.opponent = message[9:]
                print(f"\n[ИГРА] Найден соперник: {self.opponent}")
                game_state_changed = True
            elif message.startswith("SYMBOL"):
                self.my_symbol = message[7:]
                print(f"\n[ИГРА] Вы играете за: {self.my_symbol}")
                game_state_changed = True
            elif message.startswith("WAITING"):
                print(f"\n[ИГРА] {message[8:]}")
            elif message.startswith("OPPONENT_DISCONNECTED"):
                print(f"\n[ИГРА] Соперник отключился")
                self.game_active = False
                game_state_changed = True
            elif message.startswith("ERROR"):
                print(f"\n[ОШИБКА] {message[6:]}")

        
        if game_state_changed:
            self.need_display = True
            self.display_board()

        

    def show_prompt(self):
        time.sleep(0.02)
        print("\nВведите команду: ", end="", flush=True)

    def start_client(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with self.socket:
            self.socket.connect((HOST, PORT))
            print("[ПОДКЛЮЧЕНИЕ] Подключено к серверу")

            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()

            
            time.sleep(0.2)
            
            self.show_prompt()
            
            while True:
                try:
                    command = input().strip()
                    
                    if not command: 
                        self.show_prompt()
                        continue
                        
                    if command.lower() == "exit":
                        self.socket.sendall("exit".encode('utf-8'))
                        print("[ВЫХОД] Вы отключились от сервера")
                        break
                    elif command.lower() == "status":
                        self.socket.sendall("STATUS".encode('utf-8'))
                    elif command.lower().startswith("chat "):
                        self.socket.sendall(f"chat {command[5:]}".encode('utf-8'))
                    elif command.lower().startswith("move ") and self.game_active:
                        move = command[5:].strip()
                        if re.match(r'^[A-Ca-c][1-3]$', move):
                            self.socket.sendall(f"MOVE {move}".encode('utf-8'))
                        else:
                            print("Неверный формат хода. Используйте A1, B2, C3 и т.д.")
                            self.show_prompt()
                    elif re.match(r'^[A-Ca-c][1-3]$', command) and self.game_active:
                        self.socket.sendall(f"MOVE {command}".encode('utf-8'))
                    elif self.game_active:
                        print("Неизвестная команда. Доступные команды:")
                        print("  A1, B2, C3 - сделать ход")
                        print("  chat <сообщение> - отправить сообщение")
                        print("  status - запросить статус игры")
                        print("  exit - выйти из игры")
                        self.show_prompt()
                    else:
                        if command.lower().startswith("chat "):
                            self.socket.sendall(f"chat {command[5:]}".encode('utf-8'))
                        elif command.lower() == "exit":
                            self.socket.sendall("exit".encode('utf-8'))
                            print("[ВЫХОД] Вы отключились от сервера")
                            break
                        else:
                            print("Игра завершена. Доступные команды:")
                            print("  chat <сообщение> - отправить сообщение")
                            print("  exit - выйти из игры")
                            self.show_prompt()
                            
                except KeyboardInterrupt:
                    print("\n[ВЫХОД] Завершение работы...")
                    self.socket.sendall("exit".encode('utf-8'))
                    break
                except EOFError:
                    print("\n[ВЫХОД] Завершение работы...")
                    self.socket.sendall("exit".encode('utf-8'))
                    break

if __name__ == "__main__":
    client = GameClient()
    client.start_client()
