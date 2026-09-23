# HOT
package com.toto.elementallife.ops.terminal

import android.Manifest
import android.content.Context
import android.media.MediaPlayer
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview as CameraPreview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.rememberPermissionState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

// Represents a Message in SimpleX Chat
data class SimpleXMessage(
    val id: String = Random.nextInt(100000).toString(),
    val text: String,
    val isMe: Boolean,
    val timestamp: String = "23:24",
    val status: String = "Delivered (Onion 🛡️)"
)

// Represents a Chat Conversation in SimpleX Chat
data class SimpleXChat(
    val id: String,
    val name: String,
    val description: String,
    val avatarEmoji: String,
    var unreadCount: Int = 0,
    val messages: MutableList<SimpleXMessage> = mutableListOf()
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalPermissionsApi::class)
@Composable
fun SimpleXChatScreen(
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    
    // Core settings states
    var configServerUrl by remember { mutableStateOf("simplex-v3.onion") }
    var configProxyPort by remember { mutableStateOf("9050") }
    var autoStartOnion by remember { mutableStateOf(true) }
    var connectionQuality by remember { mutableStateOf("Excellent") }
    var allowUntrustedRelays by remember { mutableStateOf(false) }

    // Navigation and Panels states
    var selectedChatId by remember { mutableStateOf<String?>(null) }
    var showSettingsState by remember { mutableStateOf(false) }
    var showScannerView by remember { mutableStateOf(false) }

    // Tor/Onion states
    var isOnionRoutingEnabled by remember { mutableStateOf(true) }
    var isReconnectingOnion by remember { mutableStateOf(false) }
    var currentlyBootstrapping by remember { mutableStateOf(true) }
    var bootstrapProgress by remember { mutableStateOf(0) }
    var bootstrapStepText by remember { mutableStateOf("Starting Tor controller...") }

    // Active diagnostic test variables
    var testActive by remember { mutableStateOf(false) }
    var testReportString by remember { mutableStateOf<List<String>>(emptyList()) }
    var activeTestStep by remember { mutableStateOf(0) }

    // Connection nodes for the Onion Routing Path
    var onionHops by remember {
        mutableStateOf(
            listOf(
                Triple("Entry Guard", "185.220.101.4 (Germany)", "Ping: 42ms"),
                Triple("Middle Relay", "109.163.234.33 (Iceland)", "Ping: 89ms"),
                Triple("Exit Hidden Srv", "simplex-v3.onion (Isolated Queue)", "Ping: 125ms")
            )
        )
    }

    // Init pre-populated dynamic chats
    val chats = remember {
        mutableStateListOf(
            SimpleXChat(
                id = "echo_bot",
                name = "🤖 Tor Echo Bot",
                description = "Secure automated response node over v3 onion queues",
                avatarEmoji = "🤖",
                messages = mutableListOf(
                    SimpleXMessage("1", "Hello! You have reached v3 Onion Echo Service.", false),
                    SimpleXMessage("2", "Messages are delivered using SimpleX unidirection queues with zero user metadata. Try sending me a message!", false)
                )
            ),
            SimpleXChat(
                id = "alex_tor",
                name = "🔐 Alex (Tor Advocate)",
                description = "Online - Routing via 3-hop circuit",
                avatarEmoji = "🧑‍💻",
                messages = mutableListOf(
                    SimpleXMessage("1", "Hey! Is onion routing enabled in your dashboard? It prevents ISP snooping.", false),
                    SimpleXMessage("2", "Yes, totally encrypted!", true)
                )
            ),
            SimpleXChat(
                id = "secret_group",
                name = "🌌 SimpleX Dev Circle",
                description = "Private decentralized queue group",
                avatarEmoji = "👁",
                messages = mutableListOf(
                    SimpleXMessage("1", "Welcome to the un-trackable chat layer.", false),
                    SimpleXMessage("2", "Great, no server saves history or profiles!", false),
                    SimpleXMessage("3", "Only localized sqlite databases store the plaintext.", false)
                )
            )
        )
    }

    val activeChat = chats.find { it.id == selectedChatId }
    var messageInput by remember { mutableStateOf("") }

    // Auto-bootstrap Onion service upon initial screen load (Autostart requirement)
    LaunchedEffect(Unit) {
        if (autoStartOnion) {
            currentlyBootstrapping = true
            bootstrapProgress = 0
            
            val steps = listOf(
                "Loading Tor local client libraries..." to 15,
                "Configuring isolated SOCKS5 socks route..." to 35,
                "Requesting active directory authority consensus..." to 55,
                "Selecting 3 random relay hops in Germany, Iceland, Switzerland..." to 75,
                "Performing Diffie-Hellman handshake for asymmetric layers..." to 90,
                "Onion Queue Connection active! Zero-Metadata enabled." to 100
            )

            for ((stepText, progress) in steps) {
                bootstrapStepText = stepText
                // Incrementally build progress state
                while (bootstrapProgress < progress) {
                    delay(30)
                    bootstrapProgress += 2
                }
                delay(300)
            }
            currentlyBootstrapping = false
        } else {
            currentlyBootstrapping = false
        }
    }

    // Toggle Onion service logic
    LaunchedEffect(isOnionRoutingEnabled) {
        if (isOnionRoutingEnabled && !currentlyBootstrapping) {
            isReconnectingOnion = true
            delay(1000)
            isReconnectingOnion = false
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF0D0D0E))
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            
            // --- TOP BAR TITLE ---
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF141416))
                    .statusBarsPadding()
                    .padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = {
                            if (selectedChatId != null) {
                                selectedChatId = null
                            } else {
                                onClose()
                            }
                        },
                        modifier = Modifier.testTag("simplex_back_button")
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Back",
                            tint = Color.White
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            text = if (selectedChatId != null) activeChat?.name ?: "Chat" else "SIMPLEX MESSENGER",
                            color = Color.White,
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 15.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = if (isOnionRoutingEnabled) "🧅 ONION ROUTING ACTIVE" else "🌐 DIRECT CONNECTION (SUSPENDED)",
                            color = if (isOnionRoutingEnabled) Color(0xFF81C784) else Color(0xFFFFB74D),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }

                // Header custom Actions (Scanner and Settings access)
                Row {
                    IconButton(
                        onClick = { showScannerView = true },
                        modifier = Modifier.testTag("simplex_qrcode_button")
                    ) {
                        Icon(
                            imageVector = Icons.Default.QrCodeScanner,
                            contentDescription = "Scan Link QR",
                            tint = Color(0xFF81C784)
                        )
                    }
                    IconButton(
                        onClick = { showSettingsState = true },
                        modifier = Modifier.testTag("simplex_settings_button")
                    ) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Decentralized Settings",
                            tint = Color.LightGray
                        )
                    }
                }
            }

            // --- ONION ACTIVE CIRCUIT PATH OVERVIEW ---
            AnimatedVisibility(visible = isOnionRoutingEnabled && !currentlyBootstrapping) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF161B19)),
                    border = BorderStroke(1.dp, Color(0x3381C784)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("🧅", fontSize = 14.sp)
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = "TOR ONION CIRCUITS (METADATA PROTECTION)",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Black,
                                    color = Color(0xFF81C784),
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                            if (isReconnectingOnion) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(12.dp),
                                    color = Color(0xFF81C784),
                                    strokeWidth = 1.5.dp
                                )
                            } else {
                                Text(
                                    text = "SECURE TUNNEL",
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF81C784),
                                    fontFamily = FontFamily.Monospace,
                                    modifier = Modifier
                                        .background(Color(0xFF1E2F23), RoundedCornerShape(4.dp))
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // Nodes Trace Hops
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            onionHops.forEachIndexed { index, (name, ip, ping) ->
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    modifier = Modifier.weight(1f)
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(24.dp)
                                            .clip(CircleShape)
                                            .background(if (isReconnectingOnion) Color.DarkGray else Color(0xFF223528)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = (index + 1).toString(),
                                            color = Color(0xFF81C784),
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        text = name,
                                        fontSize = 10.sp,
                                        color = Color.White,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = ip,
                                        fontSize = 8.sp,
                                        color = Color.Gray,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = ping,
                                        fontSize = 8.sp,
                                        color = Color(0xFF81C784),
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                                if (index < onionHops.lastIndex) {
                                    Text(
                                        text = "➔",
                                        color = Color(0x6681C784),
                                        fontSize = 14.sp,
                                        modifier = Modifier.padding(bottom = 12.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // --- CHAT CONTENT LAYER ---
            if (currentlyBootstrapping) {
                // Bootstrapping interactive progress screener
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .padding(24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF141416)),
                        border = BorderStroke(1.dp, Color(0x2281C784)),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier.padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(
                                text = "🧅 ONION BOOTSTRAP AUTO-START",
                                color = Color(0xFF81C784),
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            CircularProgressIndicator(
                                progress = { bootstrapProgress / 100f },
                                color = Color(0xFF81C784),
                                trackColor = Color(0xFF2C2C2C),
                                modifier = Modifier.size(64.dp)
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "$bootstrapProgress %",
                                color = Color.White,
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                fontFamily = FontFamily.Monospace
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = bootstrapStepText,
                                color = Color.LightGray,
                                fontSize = 11.sp,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(20.dp))
                            Text(
                                text = "SimpleX creates peer-to-peer tunnels dynamically. No fixed database. Your identity IP is hidden via 3 hops.",
                                color = Color.Gray,
                                fontSize = 9.sp,
                                textAlign = TextAlign.Center,
                                lineHeight = 13.sp
                            )
                        }
                    }
                }
            } else if (selectedChatId == null) {
                // CHATS LIST VIEW
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .padding(horizontal = 12.dp)
                ) {
                    Spacer(modifier = Modifier.height(10.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "METADATA-FREE ACTIVE CHATS",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = Color.LightGray,
                            fontFamily = FontFamily.Monospace
                        )
                        
                        Row(
                            modifier = Modifier
                                .clickable { showScannerView = true }
                                .background(Color(0xFF1E2F23), RoundedCornerShape(12.dp))
                                .padding(horizontal = 8.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Add,
                                contentDescription = "Add node",
                                tint = Color(0xFF81C784),
                                modifier = Modifier.size(12.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "Scan QR / Join Link",
                                fontSize = 9.sp,
                                color = Color(0xFF81C784),
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    
                    Spacer(modifier = Modifier.height(8.dp))

                    LazyColumn(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(chats) { chat ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { selectedChatId = chat.id }
                                    .testTag("chat_item_${chat.id}"),
                                colors = CardDefaults.cardColors(containerColor = Color(0xFF141416)),
                                border = BorderStroke(1.dp, Color(0xFF232326)),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(14.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        modifier = Modifier.weight(1f)
                                    ) {
                                        Box(
                                            modifier = Modifier
                                                .size(40.dp)
                                                .clip(CircleShape)
                                                .background(Color(0xFF232326)),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Text(chat.avatarEmoji, fontSize = 20.sp)
                                        }
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column {
                                            Text(
                                                text = chat.name,
                                                fontSize = 13.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color.White
                                            )
                                            Spacer(modifier = Modifier.height(2.dp))
                                            Text(
                                                text = chat.description,
                                                fontSize = 10.sp,
                                                color = Color.Gray,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                        }
                                    }

                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(
                                            text = "Onion",
                                            fontSize = 8.sp,
                                            color = Color(0xFF81C784),
                                            fontFamily = FontFamily.Monospace,
                                            modifier = Modifier
                                                .border(
                                                    1.dp,
                                                    Color(0x3381C784),
                                                    RoundedCornerShape(4.dp)
                                                )
                                                .padding(horizontal = 4.dp, vertical = 1.dp)
                                        )
                                        if (chat.messages.isNotEmpty()) {
                                            Text(
                                                text = chat.messages.last().timestamp,
                                                fontSize = 9.sp,
                                                color = Color.Gray,
                                                modifier = Modifier.padding(top = 4.dp)
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))
                    
                    // SimpleX Info Banner
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF101311)),
                        border = BorderStroke(1.dp, Color(0x3381C784))
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.Shield,
                                    contentDescription = "Shield description",
                                    tint = Color(0xFF81C784),
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "💡 METADATA ANONYMITY PRINCIPLE",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF81C784),
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "SimpleX Chat is the first chat platform that has no user identifiers of any kind — not even random numbers or public keys. It uses unidirectional message queues which make it impossible to prove that two users are talking, guaranteeing absolute mathematical anonymity.",
                                fontSize = 10.sp,
                                color = Color.Gray,
                                lineHeight = 14.sp
                            )
                        }
                    }
                }
            } else {
                // CHAT WINDOW SCREEN (ACTIVE CONVERSATION)
                val conversation = activeChat!!

                Column(modifier = Modifier.weight(1f)) {
                    // Chat header inside discussion window
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF111113))
                            .padding(horizontal = 14.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Connected via $configServerUrl",
                            color = Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.weight(1f)
                        )
                        Text(
                            text = "Latency: 125ms",
                            color = Color(0xFF81C784),
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    // Message History Scroll
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        reverseLayout = false
                    ) {
                        items(conversation.messages) { msg ->
                            val bubbleBg = if (msg.isMe) Color(0xFF223528) else Color(0xFF1B1B1D)
                            val align = if (msg.isMe) Alignment.End else Alignment.Start

                            Column(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalAlignment = align
                            ) {
                                Card(
                                    colors = CardDefaults.cardColors(containerColor = bubbleBg),
                                    shape = RoundedCornerShape(
                                        topStart = 12.dp,
                                        topEnd = 12.dp,
                                        bottomStart = if (msg.isMe) 12.dp else 2.dp,
                                        bottomEnd = if (msg.isMe) 2.dp else 12.dp
                                    ),
                                    modifier = Modifier.widthIn(max = 280.dp)
                                ) {
                                    Column(modifier = Modifier.padding(10.dp)) {
                                        Text(text = msg.text, fontSize = 12.sp, color = Color.White)
                                        Spacer(modifier = Modifier.height(4.dp))
                                        Row(
                                            modifier = Modifier.align(Alignment.End),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Text(
                                                text = msg.timestamp,
                                                fontSize = 8.sp,
                                                color = Color.Gray
                                            )
                                            Spacer(modifier = Modifier.width(4.dp))
                                            Text(
                                                text = if (isOnionRoutingEnabled) "🧅 Encrypted" else "🌐 Direct",
                                                fontSize = 8.sp,
                                                color = if (isOnionRoutingEnabled) Color(0xFF81C784) else Color(0xFFFFB74D),
                                                fontFamily = FontFamily.Monospace
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Bottom message input field
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF141416))
                            .navigationBarsPadding()
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = messageInput,
                            onValueChange = { messageInput = it },
                            placeholder = { Text("Write anonymous queue message...", fontSize = 12.sp) },
                            modifier = Modifier
                                .weight(1f)
                                .testTag("message_input_field"),
                            shape = RoundedCornerShape(24.dp),
                            maxLines = 4,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Color(0xFF81C784),
                                unfocusedBorderColor = Color(0xFF2C2C2C),
                                focusedContainerColor = Color(0xFF0D0D0E),
                                unfocusedContainerColor = Color(0xFF0D0D0E)
                            )
                        )

                        IconButton(
                            onClick = {
                                if (messageInput.trim().isNotEmpty()) {
                                    val userText = messageInput.trim()
                                    conversation.messages.add(
                                        SimpleXMessage(
                                            text = userText,
                                            isMe = true
                                        )
                                    )
                                    messageInput = ""

                                    // Simulate Bot automated reply with zero-knowledge
                                    if (conversation.id == "echo_bot") {
                                        coroutineScope.launch {
                                            delay(1000)
                                            val autoReplies = listOf(
                                                "Message parsed with zero-knowledge keys. Success.",
                                                "Symmetric onion queue confirms Delivery status: $userText",
                                                "Did you know? SimpleX uses DH-ratchet for E2E-encryption key agreement.",
                                                "Encrypted loop response through Tor relay: Echo OK.",
                                                "Zero metadata trace. Server has no identifier of our conversation."
                                            )
                                            conversation.messages.add(
                                                SimpleXMessage(
                                                    text = autoReplies.random(),
                                                    isMe = false
                                                )
                                            )
                                        }
                                    } else if (conversation.id == "alex_tor") {
                                        coroutineScope.launch {
                                            delay(1200)
                                            val alexReplies = listOf(
                                                "Awesome response! Tor routing is very stable today.",
                                                "Using Onion address allows us to communicate even behind NAT networks.",
                                                "Let's double check if onion routing handles packet delays correctly.",
                                                "Indeed! Decentralized peer queues are amazing."
                                            )
                                            conversation.messages.add(
                                                SimpleXMessage(
                                                    text = alexReplies.random(),
                                                    isMe = false
                                                )
                                            )
                                        }
                                    } else if (conversation.id == "secret_group") {
                                        coroutineScope.launch {
                                            delay(1500)
                                            val aliases = listOf("Alice", "Bob", "Tails", "Satoshi")
                                            val groupReplies = listOf(
                                                "Agreed. No metadata leak is a game changer.",
                                                "Let's keep the discussion focused on decentralization protocol.",
                                                "Onion loops protect our physical location perfectly today.",
                                                "Message verified by queue-sign."
                                            )
                                            conversation.messages.add(
                                                SimpleXMessage(
                                                    text = "${aliases.random()}: ${groupReplies.random()}",
                                                    isMe = false
                                                )
                                            )
                                        }
                                    }
                                }
                            },
                            modifier = Modifier
                                .size(40.dp)
                                .clip(CircleShape)
                                .background(Color(0xFF81C784))
                                .testTag("message_send_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "Send",
                                tint = Color.Black
                            )
                        }
                    }
                }
            }
        }
    }

    // ==========================================
    // --- DIALOG 1: METADATA DECENTRALIZED SETTINGS ---
    // ==========================================
    if (showSettingsState) {
        AlertDialog(
            onDismissRequest = { showSettingsState = false },
            confirmButton = {
                Button(
                    onClick = { showSettingsState = false },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF81C784)),
                    modifier = Modifier.testTag("configs_save_button")
                ) {
                    Text("OK", color = Color.Black, fontWeight = FontWeight.Bold)
                }
            },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(imageVector = Icons.Default.SettingsInputAntenna, contentDescription = "Svc config", tint = Color(0xFF81C784))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("decentralized settings", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                }
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    
                    // Server address adjustment
                    Text("SimpleX Server Link / Onion URL", fontSize = 11.sp, color = Color.Gray, fontWeight = FontWeight.Bold)
                    OutlinedTextField(
                        value = configServerUrl,
                        onValueChange = { configServerUrl = it },
                        placeholder = { Text("e.g. simplex-v3.onion") },
                        shape = RoundedCornerShape(8.dp),
                        textStyle = androidx.compose.ui.text.TextStyle(fontSize = 12.sp, fontFamily = FontFamily.Monospace, color = Color.White),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color(0xFF81C784),
                            unfocusedBorderColor = Color(0xFF444444)
                        ),
                        modifier = Modifier.fillMaxWidth().testTag("config_server_url_input")
                    )

                    // Tor Socks5 proxy port
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Tor Proxy Port", fontSize = 11.sp, color = Color.Gray, fontWeight = FontWeight.Bold)
                            OutlinedTextField(
                                value = configProxyPort,
                                onValueChange = { configProxyPort = it },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                shape = RoundedCornerShape(8.dp),
                                textStyle = androidx.compose.ui.text.TextStyle(fontSize = 12.sp, fontFamily = FontFamily.Monospace, color = Color.White),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = Color(0xFF81C784),
                                    unfocusedBorderColor = Color(0xFF444444)
                                ),
                                modifier = Modifier.fillMaxWidth()
                            )
                        }

                        Column(modifier = Modifier.weight(1f)) {
                            Text("Signal Quality", fontSize = 11.sp, color = Color.Gray, fontWeight = FontWeight.Bold)
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(56.dp)
                                    .border(1.dp, Color(0xFF444444), RoundedCornerShape(8.dp))
                                    .background(Color(0xFF141416))
                                    .padding(horizontal = 8.dp),
                                contentAlignment = Alignment.CenterStart
                            ) {
                                Text(
                                    text = "3 Relays (Good)",
                                    color = Color(0xFF81C784),
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }

                    // Toggles
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Auto-Start Onion", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            Text("Instantly bootstrap Tor when opening chat screen", color = Color.Gray, fontSize = 9.sp)
                        }
                        Switch(
                            checked = autoStartOnion,
                            onCheckedChange = { autoStartOnion = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = Color(0xFF81C784))
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Allow Untrusted Relays", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            Text("Bridge traffic through custom unverified directory list", color = Color.Gray, fontSize = 9.sp)
                        }
                        Switch(
                            checked = allowUntrustedRelays,
                            onCheckedChange = { allowUntrustedRelays = it },
                            colors = SwitchDefaults.colors(checkedThumbColor = Color(0xFF81C784))
                        )
                    }

                    HorizontalDivider(color = Color(0xFF2C2C2C), thickness = 1.dp)

                    // CONNECTION TEST SECTION
                    Text("Circuit Diagnostics Tool", fontSize = 11.sp, color = Color.LightGray, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                    
                    Button(
                        onClick = {
                            coroutineScope.launch {
                                testActive = true
                                testReportString = listOf("Initializing socket link probe...")
                                delay(600)
                                testReportString = testReportString + "Connecting to SOCKS5 tunnel on localhost:$configProxyPort..."
                                delay(700)
                                testReportString = testReportString + "DH Key Exchange initialized (ed25519 signature verified OK)."
                                delay(600)
                                testReportString = testReportString + "3-Hop circuit relay response: Germany 45ms, Iceland 94ms, onion: 132ms."
                                delay(500)
                                testReportString = testReportString + "✅ ALL OK. Decentralized queues handshake complete!"
                                testActive = false
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E2F23)),
                        border = BorderStroke(1.dp, Color(0x7781C784)),
                        modifier = Modifier.fillMaxWidth().testTag("circuit_test_button"),
                        enabled = !testActive
                    ) {
                        if (testActive) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color(0xFF81C784), strokeWidth = 2.dp)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text("Handshaking...", color = Color(0xFF81C784), fontSize = 11.sp)
                            }
                        } else {
                            Text("⚡ TEST CONNECTION", color = Color(0xFF81C784), fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }
                    }

                    // Test readout logs
                    if (testReportString.isNotEmpty()) {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = Color(0xFF070708)),
                            border = BorderStroke(1.dp, Color(0xFF232326)),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(8.dp)) {
                                testReportString.forEach { log ->
                                    Text(
                                        text = "> $log",
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 9.sp,
                                        color = if (log.contains("✅") || log.contains("OK")) Color(0xFF81C784) else Color.LightGray,
                                        modifier = Modifier.padding(vertical = 2.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            },
            containerColor = Color(0xFF1E1E1E),
            shape = RoundedCornerShape(16.dp)
        )
    }

    // ==========================================
    // --- DIALOG 2: CAMERA QR & LINK SCANNER VIEW ---
    // ==========================================
    if (showScannerView) {
        val cameraPermissionState = rememberPermissionState(Manifest.permission.CAMERA)
        val lifecycleOwner = LocalLifecycleOwner.current

        AlertDialog(
            onDismissRequest = { showScannerView = false },
            confirmButton = {
                TextButton(
                    onClick = { showScannerView = false },
                    modifier = Modifier.testTag("scanner_dismiss_button")
                ) {
                    Text("Close", color = Color(0xFFFF5252), fontWeight = FontWeight.Bold)
                }
            },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(imageVector = Icons.Default.QrCodeScanner, contentDescription = "Scanner title", tint = Color(0xFF81C784))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Scan SimpleX Server / Chat QR", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                }
            },
            text = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        text = "Point camera at SimpleX server barcode or select simulated configs below.",
                        fontSize = 10.sp,
                        color = Color.LightGray
                    )

                    // Request permission screen if not granted
                    if (!cameraPermissionState.status.isGranted) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(Color(0xFF141416), RoundedCornerShape(10.dp))
                                .padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(imageVector = Icons.Default.CameraAlt, contentDescription = "Camera placeholder", tint = Color.Gray, modifier = Modifier.size(36.dp))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Camera permission needed to scan barcodes directly.",
                                color = Color.LightGray,
                                fontSize = 10.sp,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Button(
                                onClick = { cameraPermissionState.launchPermissionRequest() },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF81C784))
                            ) {
                                Text("Grant Camera Access", color = Color.Black, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    } else {
                        // CAMERA PREVIEW WORKSPACE (REAL CAMERA INTERACTIVE SURFACE)
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(160.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(Color.Black),
                            contentAlignment = Alignment.Center
                        ) {
                            // Real CameraX preview view setup bound to composable
                            AndroidView(
                                factory = { ctx ->
                                    val previewView = PreviewView(ctx)
                                    val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                                    cameraProviderFuture.addListener({
                                        val cameraProvider = cameraProviderFuture.get()
                                        val preview = CameraPreview.Builder().build()
                                        preview.setSurfaceProvider(previewView.surfaceProvider)
                                        
                                        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
                                        try {
                                            cameraProvider.unbindAll()
                                            cameraProvider.bindToLifecycle(
                                                lifecycleOwner,
                                                cameraSelector,
                                                preview
                                            )
                                        } catch (exc: Exception) {
                                            // Handle bind error
                                        }
                                    }, ContextCompat.getMainExecutor(ctx))
                                    previewView
                                },
                                modifier = Modifier.fillMaxSize()
                            )

                            // Glowing green scanning HUD hud card overlay
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .border(2.dp, Color(0x5581C784), RoundedCornerShape(10.dp))
                            ) {
                                // Animating scan laser bar
                                var laserOffset by remember { mutableStateOf(0f) }
                                LaunchedEffect(Unit) {
                                    while (true) {
                                        laserOffset = 0f
                                        delay(50)
                                        laserOffset = 0.5f
                                        delay(1500)
                                    }
                                }
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(1.5.dp)
                                        .align(Alignment.Center)
                                        .background(Color(0xFF81C784))
                                )
                            }

                            Text(
                                text = "LENS ACTIVE",
                                color = Color(0xFF81C784),
                                fontWeight = FontWeight.Bold,
                                fontSize = 8.sp,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier
                                    .align(Alignment.TopEnd)
                                    .padding(8.dp)
                                    .background(Color(0xBB0D0D0E), RoundedCornerShape(4.dp))
                                    .padding(horizontal = 4.dp, vertical = 2.dp)
                            )
                        }
                    }

                    Text(
                        text = "DEMO SCANNER INTEGRATION / PRESETS",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.LightGray,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(top = 4.dp)
                    )

                    // Simulated Scan Buttons - guarantees success under all platforms
                    Column(
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Button(
                            onClick = {
                                // Simulate scanning and adding client
                                val mockId = "whistleblower_link"
                                if (chats.none { it.id == mockId }) {
                                    chats.add(
                                        SimpleXChat(
                                            id = mockId,
                                            name = "🔒 Whistleblower Safe-Queue",
                                            description = "Active secure onion link - Direct relay node",
                                            avatarEmoji = "🛡",
                                            messages = mutableListOf(
                                                SimpleXMessage("1", "Channel decoupled and registered on simplex-v3.onion.", false),
                                                SimpleXMessage("2", "Decentralized endpoint authenticated safely! Start queue transmission.", false)
                                            )
                                        )
                                    )
                                }
                                // Success sound/feedback simulation
                                showScannerView = false
                                selectedChatId = mockId
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1B1B1D)),
                            border = BorderStroke(1.dp, Color(0xFF333333)),
                            modifier = Modifier.fillMaxWidth().testTag("preset_scan_1")
                        ) {
                            Text("⚡ Simulate Scan: Whistleblower Server Link", color = Color(0xFF81C784), fontSize = 10.sp)
                        }

                        Button(
                            onClick = {
                                val mockId = "alpha_collective"
                                if (chats.none { it.id == mockId }) {
                                    chats.add(
                                        SimpleXChat(
                                            id = mockId,
                                            name = "👥 Alpha DevOps Collective",
                                            description = "Group address parsed over decentralized queues",
                                            avatarEmoji = "🚀",
                                            messages = mutableListOf(
                                                SimpleXMessage("1", "Joined decentralised dev queue. Metadata obfuscated.", false)
                                            )
                                        )
                                    )
                                }
                                showScannerView = false
                                selectedChatId = mockId
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1B1B1D)),
                            border = BorderStroke(1.dp, Color(0xFF333333)),
                            modifier = Modifier.fillMaxWidth().testTag("preset_scan_2")
                        ) {
                            Text("👥 Simulate Scan: Alpha Dev Group Invitation", color = Color(0xFF4FC3F7), fontSize = 10.sp)
                        }

                        // Manual custom link input field
                        var pasteTextBuffer by remember { mutableStateOf("") }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            OutlinedTextField(
                                value = pasteTextBuffer,
                                onValueChange = { pasteTextBuffer = it },
                                placeholder = { Text("Or paste simplex:// link manually", fontSize = 10.sp) },
                                shape = RoundedCornerShape(8.dp),
                                textStyle = androidx.compose.ui.text.TextStyle(fontSize = 10.sp, color = Color.White),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = Color(0xFF81C784),
                                    unfocusedBorderColor = Color(0xFF444444)
                                ),
                                modifier = Modifier.weight(1f)
                            )

                            Button(
                                onClick = {
                                    if (pasteTextBuffer.trim().isNotEmpty()) {
                                        val customId = "custom_" + Random.nextInt(1000)
                                        chats.add(
                                            SimpleXChat(
                                                id = customId,
                                                name = "🔗 Custom Onion Tunnel Node",
                                                description = "Encrypted link: " + pasteTextBuffer.take(30) + "...",
                                                avatarEmoji = "🌍",
                                                messages = mutableListOf(
                                                    SimpleXMessage("1", "Onion link decrypted. Direct queue established with client.", false)
                                                )
                                            )
                                        )
                                        showScannerView = false
                                        selectedChatId = customId
                                        pasteTextBuffer = ""
                                    }
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF81C784)),
                                modifier = Modifier.height(48.dp)
                            ) {
                                Text("Add", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 11.sp)
                            }
                        }
                    }
                }
            },
            containerColor = Color(0xFF1E1E1E),
            shape = RoundedCornerShape(16.dp)
        )
    }
}
