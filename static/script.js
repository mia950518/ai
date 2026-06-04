async function sendMessage() {
    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const message = input.value.trim();
    
    if (!message) return;
    
    chatBox.innerHTML += <div class="user-message">${message}</div>;
    input.value = "";
    
    chatBox.innerHTML += <div class="bot-message">思考中...</div>;
    
    const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
    "Content-Type": "application/json"
    },
    body: JSON.stringify({ message: message })
    });
    
    const data = await response.json();
    
    const botMessages = document.querySelectorAll(".bot-message");
    botMessages[botMessages.length - 1].innerText = data.reply;
    
    chatBox.scrollTop = chatBox.scrollHeight;
    }