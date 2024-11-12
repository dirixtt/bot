import logging
import sqlite3
from telebot import TeleBot, types

# Set the logging level to INFO to capture all interactions
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize the bot with the API key
bot = TeleBot('8057397030:AAF3lYO5TadN5g9612P8QlSPtL57w0RCkjo')

# Define numeric values for different bot states
STATE_START = 0
STATE_ANONYMOUS = 1
STATE_REPLY = 2

CHANNEL_CHAT_ID = '-1002422893398'


# Function to connect to the SQLite database
def connect_to_database():
    connection = sqlite3.connect('anonqabot.db')
    cursor = connection.cursor()
    return connection, cursor


# Function to create the 'users' table in the database
def create_users_table(cursor):
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY, username TEXT)'''
    )


# Function to create the 'anonymous_messages' table in the database
def create_anonymous_messages_table(cursor):
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS anonymous_messages
        (sender_id INTEGER, recipient_id INTEGER, message TEXT, reply TEXT)'''
    )


# Function to log user activity with usernames
def log_user_message(user_id, message_text, username, reply_message=None, sender_username=None, recipient_username=None):
    log_message = f"User @{username} sent a message: {message_text}"
    if reply_message:
        log_message += f"\nAnonymous reply: {reply_message}"
    
    if sender_username and recipient_username:
        log_message += f"\nFrom user @{sender_username} to recipient @{recipient_username}"
    
    logging.info(log_message)
    bot.send_message(CHANNEL_CHAT_ID, log_message)


# Function to send a message to a recipient
def send_message_to_recipient(recipient_id, message, reply_markup=None, parse_mode=None):
    bot.send_message(recipient_id, message, reply_markup=reply_markup, parse_mode=parse_mode)


# Function to send an invitation to write an anonymous question
def send_anonymous_invitation(user_id, recipient_id):
    if user_id == recipient_id:
        message = "<b>🔗 It's your own link</b>"
    else:
        message = "<b>📥 Write your anonymous message:</b>"
    bot.send_message(user_id, message, parse_mode="HTML")


# Function to send a link for anonymous questions
def send_anonymous_link(user_id):
    message = f"<b>📨 Your link for questions:</b>\n" \
            f"<a href='t.me/{bot.get_me().username}?start={user_id}'>t.me/{bot.get_me().username}?start={user_id}</a>\n\n" \
            "🔐 Send this link to friends and followers to receive anonymous questions!"
    bot.send_message(user_id, message, parse_mode="HTML")


# Handler for the /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user_username = message.from_user.username

    # Log the /start command and send to the channel
    # log_user_message(user_id, "/start initiated", user_username)

    # Check if the command is followed by a user id to send an anonymous message
    if len(message.text.split()) > 1:
        recipient_id = int(message.text.split()[1])

        # Establish database connection and create tables if they don't exist
        connection, cursor = connect_to_database()
        create_users_table(cursor)
        create_anonymous_messages_table(cursor)

        # Insert user info into the database
        cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, user_username))
        connection.commit()

        # Log the user info insertion
        # log_user_message(user_id, f"User record created for {user_id} ({user_username})", user_username)

        # Send a message to the user to write an anonymous question
        send_anonymous_invitation(user_id, recipient_id)

        # Register the next step handler to process the message
        bot.register_next_step_handler(message, receive_message, recipient_id=recipient_id)
    else:
        # Send a link for others to send anonymous questions
        send_anonymous_link(user_id)

        # Log the link being sent
        log_user_message(user_id, "Received anonymous link", user_username)


# Handler for receiving an anonymous message
def receive_message(message, recipient_id):
    user_id = message.from_user.id
    user_message = message.text

    # Log the user's message
    user_username = message.from_user.username  # Get the username from the message
    log_user_message(user_id, user_message, user_username)  # Pass the username to the log function

    # Establish database connection
    connection, cursor = connect_to_database()

    # Check if the recipient exists in the database
    cursor.execute("SELECT id FROM users WHERE id = ?", (recipient_id,))
    recipient_exists = cursor.fetchone()

    if recipient_exists:
        # Save the anonymous message and recipient in the database
        cursor.execute("INSERT INTO anonymous_messages (sender_id, recipient_id, message) VALUES (?, ?, ?)",
                    (user_id, recipient_id, user_message))
        connection.commit()

        # Send a confirmation message to the sender
        bot.send_message(user_id, "<b>✅ Question sent!</b>\n\n"
                                f"<b>📨 Your link for questions:</b>\n"
                                f"t.me/{bot.get_me().username}?start={user_id}\n\n"
                                "🔐 Send this link to friends and followers to receive anonymous questions!",
                        parse_mode='HTML')

        # Send the message to the recipient with a "Reply" button
        send_message_to_recipient(
            recipient_id,
            f"<b>🔏 You have a new anonymous question:</b>\n\n<i>{user_message}</i>",
            reply_markup=create_reply_button(user_id),
            parse_mode="HTML"
        )

        # Log the question with usernames
        sender_username = message.from_user.username
        recipient_username = bot.get_chat(recipient_id).username if bot.get_chat(recipient_id) else "Unknown"

        # Pass the correct user_id to the log function
        log_user_message(user_id=user_id, message_text=f"Question from @{sender_username} \n Recieved @{recipient_username} \n Message: {user_message}",
                         username=sender_username, sender_username=sender_username, recipient_username=recipient_username)


    else:
        bot.send_message(user_id, "😞 Sorry, the recipient was not found.")

    # Close the database connection
    connection.close()


# Function to create a "Reply" button for the recipient
def create_reply_button(user_id):
    markup = types.InlineKeyboardMarkup()
    reply_button = types.InlineKeyboardButton("Reply Anonymously", callback_data=f"reply_{user_id}")
    markup.add(reply_button)
    return markup


# Handler for the "Reply" button
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_to_sender(call):
    sender_id = call.from_user.id
    recipient_id = int(call.data.split('_')[1])

    # Log the "Reply" button press
    logging.info(f"User {sender_id} pressed the 'Reply' button for user {recipient_id}")

    # Send a prompt for the user to write an anonymous reply
    bot.send_message(sender_id, "<b>🔏 Write an anonymous reply:</b>", parse_mode="HTML")

    # Register the next step handler to process the reply
    bot.register_next_step_handler(call.message, handle_reply, sender_id=sender_id, recipient_id=recipient_id)


def handle_reply(message, sender_id, recipient_id):
    user_message = message.text

    # Get the username of the sender
    sender_username = message.from_user.username

    # Retrieve the recipient's username, assuming you have access to the recipient data
    # You could query the database or use an API call to get the recipient's info
    recipient_user = bot.get_chat(recipient_id)  # Retrieve the recipient's info
    recipient_username = recipient_user.username if recipient_user.username else "Unknown"  # Default to "Unknown" if username is not available

    # Send the anonymous reply to the recipient
    send_message_to_recipient(
        recipient_id,
        f"<b>🔐 You have a new anonymous reply:</b>\n\n<i>{user_message}</i>",
        reply_markup=create_reply_button(sender_id),
        parse_mode="HTML"
    )

    # Send a confirmation message to the sender
    response_message = "<b>✅ Your reply has been sent!</b>\n\n"
    response_message += "Your link for questions:\n"
    response_message += f"t.me/{bot.get_me().username}?start={sender_id}\n\n"
    response_message += "Show this link to friends and followers to receive anonymous questions!"
    bot.send_message(sender_id, response_message, parse_mode="HTML")

    # Log the reply with sender username and recipient username
    log_user_message(sender_id, f"\n From: @{sender_username} \n Question from @{recipient_username} \n Message: {user_message}", sender_username)

    # If you don't need to store in SQL, just skip the database insert:
    # No database insertion

# Start the bot
bot.polling()
