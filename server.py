import sys
import socket
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QListWidget,
    QPushButton, QMessageBox, QHBoxLayout, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer

# Global Variables
HOST = '192.168.1.10'
PORT = 1111

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

rooms = {}  # {room_id: {'password': str, 'clients': [socket], 'nicknames': [str], 'admin': str}}
client_room_map = {}  # client_socket: room_id
server_running = False
server_socket_lock = threading.Lock() # To protect server socket operations during stop/start

class ServerSignals(QObject):
    update_gui = pyqtSignal()

server_signals = ServerSignals()

def broadcast(room_id, message, sender=None):
    if room_id not in rooms:
        return # Room might have been closed

    clients_to_remove = []
    for client in rooms[room_id]['clients']:
        if client != sender:
            try:
                client.send(message.encode('utf-8'))
            except:
                clients_to_remove.append(client)
    
    # Remove disconnected clients
    for client in clients_to_remove:
        remove_client_from_room(client, room_id)


def remove_client_from_room(client, room_id):
    if room_id in rooms:
        try:
            idx = rooms[room_id]['clients'].index(client)
            nickname = rooms[room_id]['nicknames'][idx]
            rooms[room_id]['clients'].pop(idx)
            rooms[room_id]['nicknames'].pop(idx)
            if client in client_room_map:
                del client_room_map[client]
            client.close()
            broadcast(room_id, f"{nickname} left the chat.")
            server_signals.update_gui.emit() # Update GUI after client leaves
        except ValueError:
            pass # Client not found in list
        except Exception as e:
            print(f"Error removing client from room: {e}")

def handle_client(client, room_id):
    nickname = None
    try:
        nickname = client.recv(1024).decode('utf-8')
        if not nickname: # Client disconnected before sending nickname
            client.close()
            return

        # Check if nickname already exists in the room
        if nickname in rooms[room_id]['nicknames']:
            client.send("NICKNAME_TAKEN".encode('utf-8')) # This message is not handled by client yet
            client.close()
            return

        rooms[room_id]['clients'].append(client)
        rooms[room_id]['nicknames'].append(nickname)
        client_room_map[client] = room_id

        if rooms[room_id]['admin'] is None:
            rooms[room_id]['admin'] = nickname
            client.send("You are the admin of this room.".encode('utf-8'))

        broadcast(room_id, f"{nickname} joined the chat.", sender=client)
        server_signals.update_gui.emit() # Update GUI after client joins

        while True:
            message = client.recv(1024).decode('utf-8')
            if not message:
                break # Client disconnected
            if message == "LEAVE_ROOM":
                break # Client explicitly left
            broadcast(room_id, f"{nickname}: {message}", sender=client)
    except ConnectionResetError:
        print(f"Client {nickname} disconnected unexpectedly from room {room_id}.")
    except Exception as e:
        print(f"Error handling client {nickname} in room {room_id}: {e}")
    finally:
        if client in client_room_map:
            remove_client_from_room(client, room_id)


def accept_connections():
    global server_running
    while server_running:
        try:
            # Set timeout to allow checking server_running flag
            server.settimeout(1.0)
            
            with server_socket_lock:
                if not server_running:
                    break
                try:
                    client, addr = server.accept()
                except socket.timeout:
                    continue  # Timeout occurred, check server_running again
            
            client.send("ROOM".encode('utf-8'))
            room_data = client.recv(1024).decode('utf-8')

            try:
                action, room_id, password = room_data.split(":", 2)
            except ValueError:
                client.send("INVALID_REQUEST".encode('utf-8'))
                client.close()
                continue

            if action == "CREATE":
                if room_id in rooms:
                    client.send("ROOM_EXISTS".encode('utf-8'))
                    client.close()
                    continue
                rooms[room_id] = {'password': password, 'clients': [], 'nicknames': [], 'admin': None}
            elif action == "JOIN":
                if room_id not in rooms:
                    client.send("NO_SUCH_ROOM".encode('utf-8'))
                    client.close()
                    continue
                if rooms[room_id]['password'] != password:
                    client.send("WRONG_PASSWORD".encode('utf-8'))
                    client.close()
                    continue
            else:
                client.send("INVALID_ACTION".encode('utf-8'))
                client.close()
                continue

            client.send("NICK".encode('utf-8'))
            threading.Thread(target=handle_client, args=(client, room_id)).start()
            server_signals.update_gui.emit() # Update GUI after room creation/join
            
        except socket.timeout:
            continue
        except OSError as e:
            if server_running: # Only print error if server was supposed to be running
                print(f"Server accept error: {e}")
            break # Server socket likely closed
        except Exception as e:
            print(f"Error in accept_connections: {e}")
            if not server_running:
                break


class ChatServerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.last_selected_room_id = None
        self.setWindowTitle("Chat Server Admin")
        self.setGeometry(300, 100, 700, 500)

        self.layout = QVBoxLayout()
        
        self.server_status_label = QLabel("Server Status: Stopped")
        self.server_status_label.setStyleSheet("font-weight: bold; color: red;")
        self.layout.addWidget(self.server_status_label)

        self.room_label = QLabel("Active Chat Rooms:")
        self.layout.addWidget(self.room_label)

        self.room_list = QListWidget()
        self.room_list.itemClicked.connect(self.display_users)
        self.layout.addWidget(self.room_list)

        self.layout.addWidget(QLabel("Users in Selected Room:"))
        self.user_list = QListWidget()
        self.layout.addWidget(self.user_list)

        self.action_buttons_layout = QHBoxLayout()
        self.kick_button = QPushButton("Kick Selected User")
        self.kick_button.clicked.connect(self.kick_user)
        self.action_buttons_layout.addWidget(self.kick_button)

        self.close_room_button = QPushButton("Close Selected Room")
        self.close_room_button.clicked.connect(self.close_room)
        self.action_buttons_layout.addWidget(self.close_room_button)
        self.layout.addLayout(self.action_buttons_layout)

        # Start/Stop Server Controls
        self.button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Server")
        self.stop_button = QPushButton("Stop Server")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_server)
        self.stop_button.clicked.connect(self.stop_server)

        self.button_layout.addWidget(self.start_button)
        self.button_layout.addWidget(self.stop_button)
        self.layout.addLayout(self.button_layout)

        self.setLayout(self.layout)
        
        server_signals.update_gui.connect(self.update_all_lists)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(2000) # Update every 2 seconds
        self.update_timer.timeout.connect(self.update_all_lists)
        self.update_timer.start()
        self.update_server_status_label()


    def update_all_lists(self):
        self.update_room_list()
        self.display_users() # Re-display users for the currently selected room

    def update_room_list(self):
        self.room_list.clear()
        for room_id, data in rooms.items():
            admin = data['admin'] if data['admin'] else "None"
            password = data['password']
            num_clients = len(data['clients'])
            self.room_list.addItem(f"{room_id} | Pass: {password} | Admin: {admin} | Users: {num_clients}")

    def display_users(self):
        self.user_list.clear()
        selected = self.room_list.currentItem()
        if selected:
           room_id = selected.text().split(" | ")[0]
           self.last_selected_room_id = room_id  # Store last selected room
        elif self.last_selected_room_id and self.last_selected_room_id in rooms:
            room_id = self.last_selected_room_id
        else:
           self.last_selected_room_id = None
           return

        if room_id in rooms:
            for user in rooms[room_id]['nicknames']:
                self.user_list.addItem(user)
        else:
            self.last_selected_room_id = None # Room no longer exists

    def kick_user(self):
        room_id = None
        room_item = self.room_list.currentItem()
        if room_item:
            room_id = room_item.text().split(" | ")[0]
            self.last_selected_room_id = room_id
        elif self.last_selected_room_id and self.last_selected_room_id in rooms:
             room_id = self.last_selected_room_id
        else:
             QMessageBox.warning(self, "Warning", "Please select a room first.")
             return

        selected_users = self.user_list.selectedItems()
        if not selected_users:
              QMessageBox.warning(self, "Warning", "Select at least one user to kick.")
              return

        if room_id not in rooms:
            QMessageBox.critical(self, "Error", "Selected room no longer exists.")
            self.update_all_lists()
            return

        for user_item in selected_users:
           user_nick = user_item.text()
           try:
             if user_nick not in rooms[room_id]['nicknames']:
                 QMessageBox.warning(self, "Warning", f"User {user_nick} is no longer in room {room_id}.")
                 continue

             index = rooms[room_id]['nicknames'].index(user_nick)
             client_to_kick = rooms[room_id]['clients'][index]

             client_to_kick.send("You have been kicked by the admin.".encode('utf-8'))
             
             # Remove client from server's tracking
             remove_client_from_room(client_to_kick, room_id)
             
             broadcast(room_id, f"{user_nick} has been kicked from the room.")
             QMessageBox.information(self, "Success", f"User {user_nick} has been kicked.")

           except ValueError:
               QMessageBox.warning(self, "Warning", f"User {user_nick} not found in room {room_id}.")
           except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not kick {user_nick}: {str(e)}")

        self.update_all_lists()

    def close_room(self):
        room_id = None
        room_item = self.room_list.currentItem()
        if room_item:
            room_id = room_item.text().split(" | ")[0]
            self.last_selected_room_id = room_id
        elif self.last_selected_room_id and self.last_selected_room_id in rooms:
             room_id = self.last_selected_room_id
        else:
             QMessageBox.warning(self, "Warning", "Please select a room to close.")
             return

        if room_id not in rooms:
            QMessageBox.critical(self, "Error", "Selected room no longer exists.")
            self.update_all_lists()
            return

        reply = QMessageBox.question(self, 'Close Room',
                                     f"Are you sure you want to close room '{room_id}'? All users will be disconnected.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if room_id in rooms:
                # Notify all clients in the room and disconnect them
                clients_to_disconnect = list(rooms[room_id]['clients']) # Create a copy
                for client in clients_to_disconnect:
                    try:
                        client.send(f"The room '{room_id}' has been closed by the admin.".encode('utf-8'))
                        remove_client_from_room(client, room_id)
                    except Exception as e:
                        print(f"Error disconnecting client during room close: {e}")
                
                del rooms[room_id]
                QMessageBox.information(self, "Room Closed", f"Room '{room_id}' has been successfully closed.")
                self.last_selected_room_id = None # Reset selected room
                self.update_all_lists()
            else:
                QMessageBox.warning(self, "Warning", f"Room '{room_id}' does not exist.")


    def update_server_status_label(self):
        if server_running:
            self.server_status_label.setText("Server Status: Running")
            self.server_status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.server_status_label.setText("Server Status: Stopped")
            self.server_status_label.setStyleSheet("font-weight: bold; color: red;")

    def start_server(self):
        global server_running, server
        if not server_running:
            try:
                with server_socket_lock:
                    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server.bind((HOST, PORT))
                    server.listen()
                    server_running = True
                
                self.server_thread = threading.Thread(target=accept_connections, daemon=True)
                self.server_thread.start()
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.update_server_status_label()
                QMessageBox.information(self, "Server Started", "Chat server is now running.")
            except Exception as e:
                QMessageBox.critical(self, "Start Error", f"Failed to start server: {e}")
                server_running = False 
                self.update_server_status_label()


    def stop_server(self):
        global server_running, server
        if server_running:
            reply = QMessageBox.question(self, 'Stop Server',
                                         "Are you sure you want to stop the server? All active connections will be terminated.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                server_running = False
                
               
                all_clients = []
                for room_id in list(rooms.keys()): # Iterate over a copy
                    for client in rooms[room_id]['clients']:
                        all_clients.append(client)
                
                for client in all_clients:
                    try:
                        client.send("The server is shutting down.".encode('utf-8'))
                        client.close()
                    except Exception as e:
                        print(f"Error notifying client during server stop: {e}")

                
                rooms.clear()
                client_room_map.clear()

                with server_socket_lock:
                    try:
                        server.shutdown(socket.SHUT_RDWR)
                        server.close()
                    except OSError as e:
                        print(f"Error shutting down server socket: {e}")
                    except Exception as e:
                        print(f"Unexpected error closing server socket: {e}")

                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.update_server_status_label()
                self.update_all_lists() # Clear lists
                QMessageBox.information(self, "Server Stopped", "Chat server has been stopped.")
            else:
                return # User cancelled stop action
        else:
            QMessageBox.information(self, "Server Status", "Server is already stopped.")

    def closeEvent(self, event):
        if server_running:
            reply = QMessageBox.question(self, 'Exit Server Admin',
                                         "The server is currently running. Do you want to stop it before exiting?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.stop_server()
                if server_running: # If stop failed or user cancelled within stop_server
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ChatServerGUI()
    gui.show()
    sys.exit(app.exec_())
