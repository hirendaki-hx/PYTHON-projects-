# 🗨️ Python Chat Application

A **client–server chat application** built with **Python sockets** and a modern **PyQt5 GUI**.  
It allows users to **create and join chat rooms** with passwords, while the server admin can **manage rooms, kick users, and shut down the server**.

## 🛠️ Built With

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/PyQt5-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Sockets](https://img.shields.io/badge/Sockets-000000?style=for-the-badge&logo=socket.io&logoColor=white)
![Threading](https://img.shields.io/badge/Threading-FFB400?style=for-the-badge&logo=python&logoColor=black)

## 🚀 Features

### Client
- Create or join chat rooms with **Room ID** and **Password**.
- Choose a **nickname** when joining.
- Send and receive real-time messages.
- Leave the room anytime.
- Automatic handling of:
  - Being kicked by the admin
  - Room closure
  - Server shutdown or disconnection

### Server (Admin GUI)
- Start and stop the chat server.
- Create and manage multiple chat rooms.
- View **active rooms** with:
  - Room ID
  - Admin nickname
  - Password
  - Number of users
- View users in each room.
- **Kick selected users** from a room.
- **Close rooms** (all users inside will be disconnected).
- Stop the entire server and disconnect all clients.

---

## 🛠️ Tech Stack
- **Python 3**
- **PyQt5** (for GUI)
- **Socket Programming** (for networking)
- **Threading** (for handling multiple clients)

---

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/pyqt5-chat-app.git
cd pyqt5-chat-app
```
### 2. Install Requirements
```bash
pip install pyqt5
```
### 3. Run the Server
```bash
python server.py
```
-Start the server from the GUI.
-The default host and port are set in server.py:
  HOST = '192.168.1.10'
  PORT = 1111
-Update these values if needed.

### 4. Run the Client
```bash
-python client.py
```
-Enter Room ID, Password, and Nickname.
-Click Create Room (to make a new one) or Join Room (to enter an existing one).





