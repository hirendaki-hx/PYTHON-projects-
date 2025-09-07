import sys
import socket
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QInputDialog, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class Communicate(QObject):
    message_received = pyqtSignal(str)
    redirect_to_start = pyqtSignal(str)

class StartWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to Chat App")
        self.setGeometry(400, 100, 400, 300)

        self.layout = QVBoxLayout()

        self.room_id_label = QLabel("Room ID:")
        self.room_id_input = QLineEdit()
        self.room_id_input.setPlaceholderText("Enter Room ID")

        self.room_pass_label = QLabel("Room Password:")
        self.room_pass_input = QLineEdit()
        self.room_pass_input.setPlaceholderText("Enter Room Password")
        self.room_pass_input.setEchoMode(QLineEdit.Password)

        self.nickname_label = QLabel("Nickname:")
        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("Enter your Nickname")

        self.create_button = QPushButton("Create Room")
        self.create_button.clicked.connect(lambda: self.attempt_connection("CREATE"))

        self.join_button = QPushButton("Join Room")
        self.join_button.clicked.connect(lambda: self.attempt_connection("JOIN"))

        self.layout.addWidget(self.room_id_label)
        self.layout.addWidget(self.room_id_input)
        self.layout.addWidget(self.room_pass_label)
        self.layout.addWidget(self.room_pass_input)
        self.layout.addWidget(self.nickname_label)
        self.layout.addWidget(self.nickname_input)
        self.layout.addWidget(self.create_button)
        self.layout.addWidget(self.join_button)

        self.setLayout(self.layout)

    def attempt_connection(self, action):
        room_id = self.room_id_input.text().strip()
        room_pass = self.room_pass_input.text().strip()
        nickname = self.nickname_input.text().strip()

        if not room_id or not room_pass or not nickname:
            QMessageBox.warning(self, "Input Error", "All fields are required.")
            return

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect(('192.168.1.10', 1111))
        except ConnectionRefusedError:
            QMessageBox.critical(self, "Connection Error", "Could not connect to the server. Server might be offline.")
            return
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"An error occurred: {e}")
            return

        # First response from server should be "ROOM"
        response = self.client_socket.recv(1024).decode('utf-8')
        if response != "ROOM":
            QMessageBox.critical(self, "Server Error", "Unexpected server response.")
            self.client_socket.close()
            return

        room_info = f"{action}:{room_id}:{room_pass}"
        self.client_socket.send(room_info.encode('utf-8'))

        response = self.client_socket.recv(1024).decode('utf-8')

        if response == "ROOM_EXISTS":
            QMessageBox.critical(self, "Error", "Room already exists with this ID. Please choose a different ID or join it.")
            self.client_socket.close()
            return
        elif response == "NO_SUCH_ROOM":
            QMessageBox.critical(self, "Error", "Room does not exist. Please create it or check the ID.")
            self.client_socket.close()
            return
        elif response == "WRONG_PASSWORD":
            QMessageBox.critical(self, "Access Denied", "Incorrect password for this room.")
            self.client_socket.close()
            return
        elif response == "INVALID_REQUEST" or response == "INVALID_ACTION":
            QMessageBox.critical(self, "Server Error", "Invalid request or action sent to server.")
            self.client_socket.close()
            return
        elif response == "NICK":
            self.client_socket.send(nickname.encode('utf-8'))
            self.open_chat_window(self.client_socket, nickname, room_id)
        else:
            QMessageBox.critical(self, "Error", f"Unknown server response: {response}")
            self.client_socket.close()


    def open_chat_window(self, client_socket, nickname, room_id):
        self.chat_window = ChatClient(client_socket, nickname, room_id)
        self.chat_window.comm.redirect_to_start.connect(self.show_start_window)
        self.chat_window.show()
        self.hide()

    def show_start_window(self, message=""):
        if message:
            QMessageBox.information(self, "Info", message)
        self.room_id_input.clear()
        self.room_pass_input.clear()
        self.nickname_input.clear()
        self.show()
        if hasattr(self, 'chat_window'):
            self.chat_window.close()


class ChatClient(QWidget):
    def __init__(self, client_socket, nickname, room_id):
        super().__init__()
        self.client = client_socket
        self.nickname = nickname
        self.room_id = room_id
        self.connected = True
        self.comm = Communicate()
        self.comm.message_received.connect(self.append_message)
        self.comm.redirect_to_start.connect(self.handle_redirect)

        self.setWindowTitle(f"Chat Client - Room: {self.room_id} - Nickname: {self.nickname}")
        self.setGeometry(400, 100, 500, 500)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter your message...")
        self.input_field.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        self.leave_button = QPushButton("Leave Room")
        self.leave_button.clicked.connect(self.leave_room)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Chat in Room: {self.room_id}"))
        layout.addWidget(self.chat_display)
        layout.addWidget(self.input_field)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.leave_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Start receiving messages
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def append_message(self, message):
        self.chat_display.append(message)

    def receive_messages(self):
        while self.connected:
            try:
                message = self.client.recv(1024).decode('utf-8')
                if not message:
                    break

                if "you have been kicked" in message.lower():
                    self.connected = False
                    self.comm.redirect_to_start.emit("You have been kicked by the admin.")
                    break
                elif "room has been closed" in message.lower():
                    self.connected = False
                    self.comm.redirect_to_start.emit(f"The room '{self.room_id}' has been closed by the admin.")
                    break
                elif "server is shutting down" in message.lower():
                    self.connected = False
                    self.comm.redirect_to_start.emit("The server is shutting down.")
                    break
                else:
                    self.comm.message_received.emit(message)

            except ConnectionResetError:
                self.connected = False
                self.comm.redirect_to_start.emit("Disconnected from server. Server might have stopped or connection lost.")
                break
            except OSError as e:
                if self.connected: # Only show error if not intentionally disconnected
                    self.comm.redirect_to_start.emit(f"Connection error: {e}")
                break
            except Exception as e:
                self.connected = False
                self.comm.redirect_to_start.emit(f"An unexpected error occurred: {e}")
                break
        self.client.close()


    def send_message(self):
        message = self.input_field.text()
        if message and self.connected:
            try:
                self.client.send(message.encode('utf-8'))
                self.chat_display.append(f"{self.nickname} (You): {message}")
                self.input_field.clear()
            except Exception as e:
                self.chat_display.append(f"Failed to send message: {e}")
                self.connected = False
                self.client.close()
                self.comm.redirect_to_start.emit("Failed to send message. Disconnected from server.")

    def leave_room(self):
        if self.connected:
            try:
                self.client.send("LEAVE_ROOM".encode('utf-8')) # Inform server
            except Exception as e:
                print(f"Error sending leave message: {e}")
            finally:
                self.connected = False
                self.client.close()
                self.comm.redirect_to_start.emit("You have left the room.")

    def handle_redirect(self, message):
        # This slot is connected to the signal that redirects to the start window
        # It will be handled by the StartWindow's show_start_window method
        pass # The signal is already connected to StartWindow's method

    def closeEvent(self, event):
        if self.connected:
            self.leave_room()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    start_window = StartWindow()
    start_window.show()
    sys.exit(app.exec_())