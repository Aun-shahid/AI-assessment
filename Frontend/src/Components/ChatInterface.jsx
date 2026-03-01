import { useState, useRef, useEffect } from "react";
import { sendMessage } from "../services/chatbot.service";
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
import LinearProgress from "@mui/material/LinearProgress";
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

/* ── state labels for the progress tracker ── */
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

const STATE_ORDER = Object.keys(STATE_LABELS);

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm **EduAssess AI** — your intelligent assessment assistant.\n\nTell me a **topic or subject area** and I'll help you create a tailored student assessment aligned to the curriculum.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [agentState, setAgentState] = useState("greeting");
  const [structuredData, setStructuredData] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

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
  const handleNewSession = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "Hello! I'm **EduAssess AI** — your intelligent assessment assistant.\n\nTell me a **topic or subject area** and I'll help you create a tailored student assessment aligned to the curriculum.",
      },
    ]);
    setSessionId(null);
    setAgentState("greeting");
    setStructuredData(null);
    setInput("");
  };

  /* ── progress ── */
  const stateIndex = STATE_ORDER.indexOf(agentState);
  const progress = ((stateIndex + 1) / STATE_ORDER.length) * 100;

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

      {/* Progress */}
      <Box sx={{ flex: 1 }}>
        <Typography variant="overline" color="text.secondary" fontWeight={600} sx={{ mb: 1, display: "block" }}>
          Progress
        </Typography>
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            height: 6,
            borderRadius: 3,
            mb: 2,
            bgcolor: "grey.200",
            "& .MuiLinearProgress-bar": {
              background: "linear-gradient(90deg, #6366f1, #818cf8)",
              borderRadius: 3,
            },
          }}
        />
        <List dense disablePadding>
          {STATE_ORDER.map((s, i) => {
            const done = i <= stateIndex;
            const active = s === agentState;
            return (
              <ListItem key={s} disableGutters sx={{ py: 0.3 }}>
                <ListItemIcon sx={{ minWidth: 28 }}>
                  {done ? (
                    <CheckCircleIcon sx={{ fontSize: 16, color: active ? "primary.dark" : "primary.main" }} />
                  ) : (
                    <RadioButtonUncheckedIcon sx={{ fontSize: 16, color: "grey.400" }} />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={STATE_LABELS[s]}
                  primaryTypographyProps={{
                    fontSize: "0.8rem",
                    fontWeight: active ? 700 : 400,
                    color: done ? (active ? "primary.dark" : "primary.main") : "text.disabled",
                  }}
                />
              </ListItem>
            );
          })}
        </List>
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
