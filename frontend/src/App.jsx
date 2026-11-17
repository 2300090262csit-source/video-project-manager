import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api(path, { method = "GET", body, form, token } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form;
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function AuthForm({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const data =
        mode === "signup"
          ? await api("/api/auth/signup", { method: "POST", body: { email, password } })
          : await api("/api/auth/login", {
              method: "POST",
              form: new URLSearchParams({ username: email, password }),
            });
      onAuth(data.access_token);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container">
      <h1>Video Project Manager</h1>
      <form className="card" onSubmit={submit}>
        <h2>{mode === "login" ? "Log in" : "Create account"}</h2>
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password (min 8 characters)" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="error">{error}</p>}
        <div className="row">
          <button type="submit">{mode === "login" ? "Log in" : "Sign up"}</button>
          <button type="button" className="secondary" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
            {mode === "login" ? "Need an account?" : "Have an account?"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ProjectsPage({ token, onOpen, onLogout }) {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setProjects(await api("/api/projects", { token }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    try {
      await api("/api/projects", { method: "POST", token, body: { name } });
      setName("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container">
      <div className="row">
        <h1>My Projects</h1>
        <button className="secondary" onClick={onLogout}>Log out</button>
      </div>
      <form className="card" onSubmit={create}>
        <input placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} required />
        <button type="submit">Create project</button>
      </form>
      {error && <p className="error">{error}</p>}
      {projects.map((p) => (
        <div className="card row" key={p.id}>
          <div>
            <strong>{p.name}</strong>
            <div className="muted">Created {new Date(p.created_at).toLocaleDateString()}</div>
          </div>
          <button onClick={() => onOpen(p)}>Open</button>
        </div>
      ))}
    </div>
  );
}

function ProjectDetail({ token, project, onBack }) {
  const [clips, setClips] = useState([]);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const qs = search ? `?q=${encodeURIComponent(search)}` : "";
      setClips(await api(`/api/projects/${project.id}/clips${qs}`, { token }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, [search]);

  async function upload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api(`/api/projects/${project.id}/clips`, { method: "POST", token, form });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function addTag(clip, tagName) {
    if (!tagName.trim()) return;
    await api(`/api/clips/${clip.id}/tags`, { method: "POST", token, body: { name: tagName } });
    load();
  }

  async function addVersion(clip, note) {
    if (!note.trim()) return;
    await api(`/api/clips/${clip.id}/versions`, { method: "POST", token, body: { note } });
    load();
  }

  return (
    <div className="container">
      <button className="secondary" onClick={onBack}>← Back</button>
      <h1>{project.name}</h1>
      <div className="card">
        <label>Upload clip: </label>
        <input type="file" accept="video/*,audio/*,image/*" onChange={upload} disabled={uploading} />
        {uploading && <p className="muted">Uploading...</p>}
      </div>
      <input placeholder="Search clips by name" value={search} onChange={(e) => setSearch(e.target.value)} />
      {error && <p className="error">{error}</p>}
      {clips.map((clip) => (
        <ClipCard key={clip.id} clip={clip} onAddTag={addTag} onAddVersion={addVersion} />
      ))}
    </div>
  );
}

function ClipCard({ clip, onAddTag, onAddVersion }) {
  const [tag, setTag] = useState("");
  const [note, setNote] = useState("");

  return (
    <div className="card">
      <div className="row">
        <strong>{clip.filename}</strong>
        <span className="muted">{(clip.size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
      </div>
      <div>
        {clip.tags.map((t) => <span className="tag" key={t.id}>{t.name}</span>)}
      </div>
      <div className="row">
        <input placeholder="Add tag" value={tag} onChange={(e) => setTag(e.target.value)} />
        <button className="secondary" onClick={() => { onAddTag(clip, tag); setTag(""); }}>Tag</button>
      </div>
      <div className="muted">Versions: {clip.versions.length}</div>
      {clip.versions.map((v) => (
        <div className="muted" key={v.id}>v{v.number}: {v.note}</div>
      ))}
      <div className="row">
        <input placeholder="Version note, e.g. Color graded" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="secondary" onClick={() => { onAddVersion(clip, note); setNote(""); }}>Save version</button>
      </div>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [openProject, setOpenProject] = useState(null);

  function handleAuth(newToken) {
    localStorage.setItem("token", newToken);
    setToken(newToken);
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setOpenProject(null);
  }

  if (!token) return <AuthForm onAuth={handleAuth} />;
  if (openProject) {
    return <ProjectDetail token={token} project={openProject} onBack={() => setOpenProject(null)} />;
  }
  return <ProjectsPage token={token} onOpen={setOpenProject} onLogout={logout} />;
}
