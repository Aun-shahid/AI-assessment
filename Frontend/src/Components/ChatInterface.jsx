import { useState, useRef, useEffect, useCallback } from "react";
import {
  sendMessage,
  listSessions,
  getSession,
  createSession,
  deleteSession,
} from "../services/chatbot.service";
import ReactMarkdown from "react-markdown";

// MUI
import { createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Avatar from "@mui/material/Avatar";
import Paper from "@mui/material/Paper";
import Chip from "@mui/material/Chip";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Fade from "@mui/material/Fade";
import CircularProgress from "@mui/material/CircularProgress";
import useMediaQuery from "@mui/material/useMediaQuery";

// MUI Icons
import MenuBookIcon from "@mui/icons-material/MenuBook";
import AddIcon from "@mui/icons-material/Add";
import SendIcon from "@mui/icons-material/Send";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import MenuIcon from "@mui/icons-material/Menu";
import AssignmentTurnedInIcon from "@mui/icons-material/AssignmentTurnedIn";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";

/* ── Theme ── */
const theme = createTheme({
  palette: {
    primary: { main: "#6366f1", light: "#818cf8", dark: "#4f46e5" },
    background: { default: "#f8fafc", paper: "#ffffff" },
    text: { primary: "#1e293b", secondary: "#64748b" },
  },
  typography: {
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: "none", fontWeight: 600 },
      },
    },
  },
});

const DRAWER_WIDTH = 280;

/* ── state labels for the current-step indicator ── */
const STATE_LABELS = {
  greeting: "Getting started",
  topic_identification: "Identifying topics",
  domain_reasoning: "Matching learning outcomes",
  topic_selection: "Selecting topics",
  content_retrieval: "Retrieving content",
  review_refinement: "Reviewing & refining",
  assessment_generation: "Generating assessment",
  complete: "Assessment ready",
};

const DEFAULT_GREETING = {
  role: "assistant",
  content:
    "Hello! I'm **EduAssess AI** — your intelligent assessment assistant.\n\nTell me a **topic or subject area** and I'll help you create a tailored student assessment aligned to the curriculum.",
};

export default function ChatInterface() {
  const [messages, setMessages] = useState([DEFAULT_GREETING]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [agentState, setAgentState] = useState("greeting");
  const [structuredData, setStructuredData] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Session list state
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  // ── Fetch sessions list ──
  const fetchSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      const res = await listSessions(0, 50);
      setSessions(res.sessions);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  /* auto-scroll on new messages */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  /* keep input focused */
  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  /* ── send handler ── */
  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendMessage({ session_id: sessionId, message: text });
      setSessionId(res.session_id);
      setAgentState(res.state);
      if (res.data) setStructuredData(res.data);
      setMessages((prev) => [...prev, { role: "assistant", content: res.response }]);
      // Refresh session list so the sidebar stays current
      fetchSessions();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ Something went wrong — please try again.\n\n\`${err.message}\`` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ── new session ── */
  const handleNewSession = async () => {
    setMessages([DEFAULT_GREETING]);
    setSessionId(null);
    setAgentState("greeting");
    setStructuredData(null);
    setInput("");
    if (isMobile) setMobileOpen(false);

    try {
      const res = await createSession();
      setSessionId(res.session_id);
      fetchSessions();
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  /* ── load an existing session ── */
  const handleLoadSession = async (sid) => {
    if (sid === sessionId) return;
    try {
      setLoading(true);
      const detail = await getSession(sid);

      // Restore messages — if empty, show default greeting
      if (detail.messages && detail.messages.length > 0) {
        setMessages(
          detail.messages.map((m) => ({ role: m.role, content: m.content }))
        );
      } else {
        setMessages([DEFAULT_GREETING]);
      }

      setSessionId(detail.session_id);
      setAgentState(detail.state);
      setStructuredData(
        detail.generated_assessment
          ? { assessment: detail.generated_assessment }
          : detail.selected_los?.length
          ? { selected_los: detail.selected_los }
          : null
      );
      setInput("");
      if (isMobile) setMobileOpen(false);
    } catch (err) {
      console.error("Failed to load session:", err);
    } finally {
      setLoading(false);
    }
  };

  /* ── delete a session ── */
  const handleDeleteSession = async (sid, e) => {
    e.stopPropagation(); // Prevent triggering the load handler
    try {
      await deleteSession(sid);
      // If we deleted the active session, reset to a blank state
      if (sid === sessionId) {
        setMessages([DEFAULT_GREETING]);
        setSessionId(null);
        setAgentState("greeting");
        setStructuredData(null);
        setInput("");
      }
      fetchSessions();
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  /* ── Sidebar content ── */
  const sidebarContent = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", p: 2, gap: 2 }}>
      {/* Brand */}
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ py: 1 }}>
        <Avatar sx={{ bgcolor: "primary.main", width: 40, height: 40, borderRadius: 2.5 }}>
          <MenuBookIcon />
        </Avatar>
        <Typography variant="h6" fontWeight={700} letterSpacing="-0.02em">
          EduAssess
        </Typography>
      </Stack>

      {/* New Assessment */}
      <Button
        variant="outlined"
        startIcon={<AddIcon />}
        onClick={handleNewSession}
        fullWidth
        sx={{
          borderStyle: "dashed",
          color: "text.secondary",
          borderColor: "divider",
          "&:hover": { borderColor: "primary.main", color: "primary.main", bgcolor: "primary.main", background: "rgba(99,102,241,0.04)" },
        }}
      >
        New Assessment
      </Button>

      <Divider />

      {/* Session History */}
      <Box sx={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <Typography variant="overline" color="text.secondary" fontWeight={600} sx={{ mb: 0.5, display: "block" }}>
          Sessions
        </Typography>

        {/* Session list — scrollable */}
        <Box
          sx={{
            flex: 1,
            overflowY: "auto",
            mb: 1,
            "&::-webkit-scrollbar": { width: 4 },
            "&::-webkit-scrollbar-thumb": { bgcolor: "grey.300", borderRadius: 2 },
          }}
        >
          {sessionsLoading && sessions.length === 0 ? (
            <Typography variant="caption" color="text.disabled" sx={{ px: 1 }}>
              Loading…
            </Typography>
          ) : sessions.length === 0 ? (
            <Typography variant="caption" color="text.disabled" sx={{ px: 1 }}>
              No sessions yet
            </Typography>
          ) : (
            sessions.map((s) => {
              const isActive = s.session_id === sessionId;
              return (
                <Paper
                  key={s.session_id}
                  elevation={0}
                  onClick={() => handleLoadSession(s.session_id)}
                  sx={{
                    p: 1,
                    mb: 0.5,
                    cursor: "pointer",
                    borderRadius: 2,
                    border: 1,
                    borderColor: isActive ? "primary.main" : "transparent",
                    bgcolor: isActive ? "rgba(99,102,241,0.06)" : "transparent",
                    "&:hover": {
                      bgcolor: isActive ? "rgba(99,102,241,0.1)" : "grey.50",
                    },
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    transition: "all 0.15s ease",
                  }}
                >
                  <ChatBubbleOutlineIcon
                    sx={{ fontSize: 16, color: isActive ? "primary.main" : "text.disabled", flexShrink: 0 }}
                  />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="body2"
                      noWrap
                      sx={{
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? "primary.dark" : "text.primary",
                        fontSize: "0.8rem",
                      }}
                    >
                      {s.last_message_preview || STATE_LABELS[s.state] || "New session"}
                    </Typography>
                    <Typography variant="caption" color="text.disabled" sx={{ fontSize: "0.65rem" }}>
                      {new Date(s.updated_at).toLocaleDateString()}
                    </Typography>
                  </Box>
                  <IconButton
                    size="small"
                    onClick={(e) => handleDeleteSession(s.session_id, e)}
                    sx={{
                      opacity: 0.4,
                      "&:hover": { opacity: 1, color: "error.main" },
                      p: 0.3,
                    }}
                  >
                    <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Paper>
              );
            })
          )}
        </Box>

        <Divider sx={{ mb: 1 }} />
      </Box>

      {/* Assessment ready card */}
      {structuredData?.assessment && (
        <Paper variant="outlined" sx={{ p: 2, bgcolor: "rgba(99,102,241,0.06)", borderColor: "primary.light" }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
            <AssignmentTurnedInIcon sx={{ fontSize: 18, color: "primary.main" }} />
            <Typography variant="subtitle2" color="primary.dark">Assessment Ready</Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Your assessment has been generated. View it in the chat.
          </Typography>
        </Paper>
      )}
    </Box>
  );

  /* ── Render ── */
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", height: "100vh" }}>
        {/* ── Sidebar ── */}
        {isMobile ? (
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            sx={{ "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" } }}
          >
            {sidebarContent}
          </Drawer>
        ) : (
          <Drawer
            variant="permanent"
            sx={{
              width: DRAWER_WIDTH,
              flexShrink: 0,
              "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", borderRight: "1px solid", borderColor: "divider" },
            }}
          >
            {sidebarContent}
          </Drawer>
        )}

        {/* ── Main ── */}
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          {/* Header */}
          <AppBar
            position="static"
            elevation={0}
            sx={{ bgcolor: "background.paper", borderBottom: 1, borderColor: "divider" }}
          >
            <Toolbar sx={{ gap: 1.5 }}>
              {isMobile && (
                <IconButton edge="start" onClick={() => setMobileOpen(true)}>
                  <MenuIcon />
                </IconButton>
              )}
              <Typography variant="h6" fontWeight={700} color="text.primary" sx={{ flexGrow: 1 }}>
                AI Assessment Builder
              </Typography>
              <Chip
                label={STATE_LABELS[agentState] || agentState}
                size="small"
                sx={{
                  bgcolor: "rgba(99,102,241,0.08)",
                  color: "primary.main",
                  fontWeight: 600,
                  fontSize: "0.75rem",
                }}
              />
              {sessionId && (
                <Typography variant="caption" color="text.disabled" sx={{ fontFamily: "monospace" }}>
                  {sessionId.slice(0, 8)}…
                </Typography>
              )}
            </Toolbar>
          </AppBar>

          {/* Messages */}
          <Box
            sx={{
              flex: 1,
              overflowY: "auto",
              px: { xs: 2, md: 4 },
              py: 3,
              display: "flex",
              flexDirection: "column",
              gap: 2.5,
              "&::-webkit-scrollbar": { width: 6 },
              "&::-webkit-scrollbar-thumb": { bgcolor: "grey.300", borderRadius: 3 },
            }}
          >
            {messages.map((msg, i) => {
              const isUser = msg.role === "user";
              return (
                <Fade in key={i} timeout={400}>
                  <Stack
                    direction="row"
                    spacing={1.5}
                    sx={{
                      alignSelf: isUser ? "flex-end" : "flex-start",
                      flexDirection: isUser ? "row-reverse" : "row",
                      maxWidth: { xs: "95%", md: "75%" },
                    }}
                  >
                    <Avatar
                      sx={{
                        width: 36,
                        height: 36,
                        bgcolor: isUser ? "primary.main" : "rgba(99,102,241,0.1)",
                        color: isUser ? "#fff" : "primary.main",
                      }}
                    >
                      {isUser ? <PersonIcon fontSize="small" /> : <SmartToyIcon fontSize="small" />}
                    </Avatar>
                    <Paper
                      elevation={0}
                      sx={{
                        p: 2,
                        borderRadius: 3,
                        ...(isUser
                          ? {
                              background: "linear-gradient(135deg, #6366f1, #4f46e5)",
                              color: "#fff",
                              borderTopRightRadius: 4,
                              "& a": { color: "#c7d2fe" },
                              "& code": { bgcolor: "rgba(255,255,255,0.15)", px: 0.5, borderRadius: 1 },
                            }
                          : {
                              bgcolor: "background.paper",
                              border: 1,
                              borderColor: "divider",
                              borderTopLeftRadius: 4,
                              "& code": { bgcolor: "grey.100", px: 0.5, borderRadius: 1, fontSize: "0.85em" },
                              "& pre": { bgcolor: "#1e293b", color: "#e2e8f0", p: 2, borderRadius: 2, overflowX: "auto", fontSize: "0.85rem" },
                            }),
                        "& p": { m: 0, mb: 1, lineHeight: 1.65, "&:last-child": { mb: 0 } },
                        "& ul, & ol": { my: 1, pl: 2.5 },
                        "& li": { mb: 0.5 },
                        fontSize: "0.925rem",
                      }}
                    >
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </Paper>
                  </Stack>
                </Fade>
              );
            })}

            {/* Typing indicator */}
            {loading && (
              <Fade in timeout={300}>
                <Stack direction="row" spacing={1.5} sx={{ alignSelf: "flex-start" }}>
                  <Avatar sx={{ width: 36, height: 36, bgcolor: "rgba(99,102,241,0.1)", color: "primary.main" }}>
                    <SmartToyIcon fontSize="small" />
                  </Avatar>
                  <Paper
                    elevation={0}
                    sx={{ px: 3, py: 2, borderRadius: 3, border: 1, borderColor: "divider", borderTopLeftRadius: 4, display: "flex", alignItems: "center", gap: 0.8 }}
                  >
                    {[0, 200, 400].map((delay) => (
                      <FiberManualRecordIcon
                        key={delay}
                        sx={{
                          fontSize: 10,
                          color: "primary.light",
                          animation: "bounce 1.4s infinite ease-in-out both",
                          animationDelay: `${delay}ms`,
                          "@keyframes bounce": {
                            "0%, 80%, 100%": { transform: "scale(0.6)", opacity: 0.4 },
                            "40%": { transform: "scale(1)", opacity: 1 },
                          },
                        }}
                      />
                    ))}
                  </Paper>
                </Stack>
              </Fade>
            )}
            <div ref={bottomRef} />
          </Box>

          {/* Input bar */}
          <Paper
            component="form"
            elevation={0}
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            sx={{
              display: "flex",
              alignItems: "flex-end",
              gap: 1.5,
              px: { xs: 2, md: 4 },
              py: 2,
              borderTop: 1,
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <TextField
              inputRef={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe the topic you'd like to assess…"
              disabled={loading}
              multiline
              maxRows={4}
              fullWidth
              variant="outlined"
              size="small"
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 3,
                  bgcolor: "grey.50",
                  "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                    borderColor: "primary.main",
                    boxShadow: "0 0 0 3px rgba(99,102,241,0.12)",
                  },
                },
              }}
            />
            <IconButton
              type="submit"
              disabled={loading || !input.trim()}
              sx={{
                width: 44,
                height: 44,
                background: "linear-gradient(135deg, #6366f1, #4f46e5)",
                color: "#fff",
                "&:hover": { transform: "scale(1.05)", boxShadow: "0 4px 14px rgba(99,102,241,0.35)" },
                "&.Mui-disabled": { background: "grey.300", color: "grey.500" },
                transition: "all 0.2s ease",
              }}
            >
              {loading ? <CircularProgress size={20} sx={{ color: "#fff" }} /> : <SendIcon fontSize="small" />}
            </IconButton>
          </Paper>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
