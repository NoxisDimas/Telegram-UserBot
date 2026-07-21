import { useState, useEffect } from 'react';
import { Lock, Eye, EyeOff, Loader2, CheckCircle, Shield, Users as UsersIcon, Settings, Plus, Trash2, Edit2, ShieldAlert, Ban } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api/client';
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import Badge from '../components/Badge';

function getPasswordStrength(pw) {
  if (!pw) return { score: 0, label: '', color: '' };
  let s = 0;
  if (pw.length >= 6) s++;
  if (pw.length >= 10) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  const levels = [
    { label: 'Very Weak', color: 'bg-danger' },
    { label: 'Weak', color: 'bg-danger' },
    { label: 'Fair', color: 'bg-warning' },
    { label: 'Good', color: 'bg-neon-dim' },
    { label: 'Strong', color: 'bg-neon' },
    { label: 'Very Strong', color: 'bg-neon' },
  ];
  return { score: s, ...levels[s] };
}

const roleColors = {
  OWNER: 'danger',
  ADMIN: 'warning',
  STAFF: 'info',
  USER: 'neutral'
};

export default function Users() {
  const [activeTab, setActiveTab] = useState('admins');

  // --- Settings State ---
  const [form, setForm] = useState({ old_password: '', new_password: '', confirm_password: '' });
  const [show, setShow] = useState({ old: false, new: false, confirm: false });
  const [submittingSettings, setSubmittingSettings] = useState(false);

  // --- Admins State ---
  const [admins, setAdmins] = useState([]);
  const [loadingAdmins, setLoadingAdmins] = useState(false);
  const [showAddAdmin, setShowAddAdmin] = useState(false);
  const [addAdminForm, setAddAdminForm] = useState({ username: '', password: '' });
  const [adminDeleteTarget, setAdminDeleteTarget] = useState(null);
  const [submittingAdmin, setSubmittingAdmin] = useState(false);

  // --- Bot Users State ---
  const [botUsers, setBotUsers] = useState([]);
  const [loadingBotUsers, setLoadingBotUsers] = useState(false);
  const [roleUpdateTarget, setRoleUpdateTarget] = useState(null);
  const [newRole, setNewRole] = useState('USER');
  const [submittingRole, setSubmittingRole] = useState(false);
  
  useEffect(() => {
    if (activeTab === 'admins') fetchAdmins();
    else if (activeTab === 'bot_users') fetchBotUsers();
  }, [activeTab]);

  // --- API Calls: Settings ---
  const handleSettingsSubmit = async (e) => {
    e.preventDefault();
    if (form.new_password !== form.confirm_password) return toast.error('New passwords do not match');
    if (form.new_password.length < 6) return toast.error('Password must be at least 6 characters');

    setSubmittingSettings(true);
    try {
      await api.put('/users/password', { old_password: form.old_password, new_password: form.new_password });
      toast.success('Password updated successfully!');
      setForm({ old_password: '', new_password: '', confirm_password: '' });
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to update password'); }
    finally { setSubmittingSettings(false); }
  };

  // --- API Calls: Admins ---
  const fetchAdmins = async () => {
    setLoadingAdmins(true);
    try { const res = await api.get('/users/admins'); setAdmins(res.data); }
    catch { toast.error('Failed to load admins'); }
    finally { setLoadingAdmins(false); }
  };

  const handleAddAdmin = async (e) => {
    e.preventDefault();
    if (addAdminForm.password.length < 6) return toast.error('Password must be at least 6 characters');
    setSubmittingAdmin(true);
    try {
      await api.post('/users/admins', addAdminForm);
      toast.success('Admin created successfully!');
      setShowAddAdmin(false);
      setAddAdminForm({ username: '', password: '' });
      fetchAdmins();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to create admin'); }
    finally { setSubmittingAdmin(false); }
  };

  const handleDeleteAdmin = async () => {
    if (!adminDeleteTarget) return;
    setSubmittingAdmin(true);
    try {
      await api.delete(`/users/admins/${adminDeleteTarget.id}`);
      toast.success('Admin deleted successfully!');
      setAdminDeleteTarget(null);
      fetchAdmins();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to delete admin'); }
    finally { setSubmittingAdmin(false); }
  };

  // --- API Calls: Bot Users ---
  const fetchBotUsers = async () => {
    setLoadingBotUsers(true);
    try { const res = await api.get('/users/bot-users'); setBotUsers(res.data); }
    catch { toast.error('Failed to load bot users'); }
    finally { setLoadingBotUsers(false); }
  };

  const handleUpdateRole = async () => {
    if (!roleUpdateTarget) return;
    setSubmittingRole(true);
    try {
      await api.put(`/users/bot-users/${roleUpdateTarget.user_id}/role`, { role: newRole });
      toast.success('Role updated successfully!');
      setRoleUpdateTarget(null);
      fetchBotUsers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to update role'); }
    finally { setSubmittingRole(false); }
  };

  const handleToggleBan = async (user) => {
    const is_banned = !user.is_banned;
    try {
      await api.put(`/users/bot-users/${user.user_id}/ban`, { is_banned });
      toast.success(is_banned ? 'User banned' : 'User unbanned');
      fetchBotUsers();
    } catch (err) { toast.error('Failed to update ban status'); }
  };

  // --- Table Columns ---
  const adminColumns = [
    { key: 'username', label: 'Username', render: (r) => <span className="font-medium text-text-primary">{r.username}</span> },
    { key: 'is_default', label: 'Type', render: (r) => r.is_default ? <Badge variant="warning">Default Admin</Badge> : <Badge variant="neutral">Admin</Badge> },
    { key: 'created_at', label: 'Created At', render: (r) => <span className="text-sm text-text-muted">{new Date(r.created_at).toLocaleDateString()}</span> },
    { key: 'actions', label: '', render: (r) => !r.is_default && (
      <button onClick={() => setAdminDeleteTarget(r)} className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors" title="Delete Admin">
        <Trash2 className="w-4 h-4" />
      </button>
    )}
  ];

  const botUserColumns = [
    { key: 'user_id', label: 'ID', render: (r) => <span className="text-sm text-text-muted font-mono">{r.user_id}</span> },
    { key: 'name', label: 'Name', render: (r) => (
      <div>
        <p className="text-sm text-text-primary font-medium">{r.first_name || 'Unknown'}</p>
        {r.username && <p className="text-xs text-text-muted">@{r.username}</p>}
      </div>
    )},
    { key: 'role', label: 'Role', render: (r) => <Badge variant={roleColors[r.role] || 'neutral'}>{r.role}</Badge> },
    { key: 'status', label: 'Status', render: (r) => r.is_banned ? <Badge variant="danger">Banned</Badge> : <Badge variant="success">Active</Badge> },
    { key: 'joined', label: 'Joined', render: (r) => <span className="text-sm text-text-muted">{new Date(r.created_at).toLocaleDateString()}</span> },
    { key: 'actions', label: '', render: (r) => (
      <div className="flex gap-2">
        <button onClick={() => { setRoleUpdateTarget(r); setNewRole(r.role); }} className="p-2 text-text-muted hover:text-neon hover:bg-neon/10 rounded-lg transition-colors" title="Change Role">
          <ShieldAlert className="w-4 h-4" />
        </button>
        <button onClick={() => handleToggleBan(r)} className={`p-2 rounded-lg transition-colors ${r.is_banned ? 'text-success hover:bg-success/10' : 'text-danger hover:bg-danger/10'}`} title={r.is_banned ? 'Unban User' : 'Ban User'}>
          {r.is_banned ? <CheckCircle className="w-4 h-4" /> : <Ban className="w-4 h-4" />}
        </button>
      </div>
    )}
  ];

  const strength = getPasswordStrength(form.new_password);
  const match = form.new_password && form.confirm_password && form.new_password === form.confirm_password;
  const mismatch = form.confirm_password && form.new_password !== form.confirm_password;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">User Management</h1>
        <p className="text-sm text-text-muted mt-1.5">Manage dashboard admins and Telegram bot users.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-border">
        <button onClick={() => setActiveTab('admins')} className={`pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2 ${activeTab === 'admins' ? 'border-neon text-neon' : 'border-transparent text-text-muted hover:text-text-primary'}`}>
          <Shield className="w-4 h-4" /> Dashboard Admins
        </button>
        <button onClick={() => setActiveTab('bot_users')} className={`pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2 ${activeTab === 'bot_users' ? 'border-neon text-neon' : 'border-transparent text-text-muted hover:text-text-primary'}`}>
          <UsersIcon className="w-4 h-4" /> Telegram Users
        </button>
        <button onClick={() => setActiveTab('settings')} className={`pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2 ${activeTab === 'settings' ? 'border-neon text-neon' : 'border-transparent text-text-muted hover:text-text-primary'}`}>
          <Settings className="w-4 h-4" /> My Settings
        </button>
      </div>

      {/* --- Admins Tab --- */}
      {activeTab === 'admins' && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-text-primary">Dashboard Admins</h2>
            <button onClick={() => setShowAddAdmin(true)} className="btn-primary">
              <Plus className="w-4 h-4" /> Create Admin
            </button>
          </div>
          <DataTable columns={adminColumns} data={admins} loading={loadingAdmins} />
        </div>
      )}

      {/* --- Bot Users Tab --- */}
      {activeTab === 'bot_users' && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-text-primary">Telegram Bot Users</h2>
          </div>
          <DataTable columns={botUserColumns} data={botUsers} loading={loadingBotUsers} />
        </div>
      )}

      {/* --- Settings Tab --- */}
      {activeTab === 'settings' && (
        <div className="card overflow-hidden animate-fade-in">
          <div className="flex items-center gap-4 px-6 lg:px-8 py-5 border-b border-border">
            <div className="w-10 h-10 rounded-xl bg-neon/8 border border-neon/20 flex items-center justify-center">
              <Lock className="w-5 h-5 text-neon" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-text-primary">Change Password</h2>
              <p className="text-xs text-text-muted mt-0.5">Update your own admin password</p>
            </div>
          </div>

          <form onSubmit={handleSettingsSubmit} className="p-6 lg:p-8 space-y-5">
            <div>
              <label className="block mb-2 text-sm font-medium text-text-secondary">Current Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type={show.old ? 'text' : 'password'} value={form.old_password} onChange={(e) => setForm({ ...form, old_password: e.target.value })} required placeholder="••••••••" className="input-field pl-11 pr-11" />
                <button type="button" onClick={() => setShow({ ...show, old: !show.old })} className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors">
                  {show.old ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block mb-2 text-sm font-medium text-text-secondary">New Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type={show.new ? 'text' : 'password'} value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} required placeholder="••••••••" className="input-field pl-11 pr-11" />
                <button type="button" onClick={() => setShow({ ...show, new: !show.new })} className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors">
                  {show.new ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {form.new_password && (
              <div className="animate-fade-in">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-muted">Password strength</span>
                  <span className={`text-xs font-medium ${strength.score <= 1 ? 'text-danger' : strength.score <= 2 ? 'text-warning' : 'text-neon'}`}>{strength.label}</span>
                </div>
                <div className="w-full h-2 bg-border rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-500 ${strength.color}`} style={{ width: `${(strength.score / 5) * 100}%` }} />
                </div>
              </div>
            )}

            <div>
              <label className="block mb-2 text-sm font-medium text-text-secondary">Confirm New Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type={show.confirm ? 'text' : 'password'} value={form.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} required placeholder="••••••••" className="input-field pl-11 pr-11" />
                <button type="button" onClick={() => setShow({ ...show, confirm: !show.confirm })} className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors">
                  {show.confirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {form.confirm_password && (
              <div className="animate-fade-in">
                {match && <p className="text-xs text-neon flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5" /> Passwords match</p>}
                {mismatch && <p className="text-xs text-danger">Passwords do not match</p>}
              </div>
            )}

            <div className="pt-3">
              <button type="submit" disabled={submittingSettings || !match} className="btn-primary w-full">
                {submittingSettings ? <><Loader2 className="w-4 h-4 animate-spin" /> Updating...</> : 'Update Password'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* --- Modals --- */}
      
      {/* Add Admin Modal */}
      <Modal isOpen={showAddAdmin} onClose={() => setShowAddAdmin(false)} title="Create Admin" size="sm">
        <form onSubmit={handleAddAdmin} className="space-y-4">
          <div>
            <label className="block text-sm text-text-muted mb-1">Username</label>
            <input type="text" className="input-field" value={addAdminForm.username} onChange={e => setAddAdminForm({...addAdminForm, username: e.target.value})} required />
          </div>
          <div>
            <label className="block text-sm text-text-muted mb-1">Password</label>
            <input type="password" className="input-field" value={addAdminForm.password} onChange={e => setAddAdminForm({...addAdminForm, password: e.target.value})} required minLength={6} />
          </div>
          <div className="pt-4 flex justify-end gap-3 border-t border-border mt-6">
            <button type="button" onClick={() => setShowAddAdmin(false)} className="btn-secondary">Cancel</button>
            <button type="submit" className="btn-primary" disabled={submittingAdmin}>
              {submittingAdmin ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Admin'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Admin Modal */}
      <Modal isOpen={!!adminDeleteTarget} onClose={() => setAdminDeleteTarget(null)} title="Delete Admin" size="sm"
        footer={
          <>
            <button onClick={() => setAdminDeleteTarget(null)} className="btn-secondary">Cancel</button>
            <button onClick={handleDeleteAdmin} disabled={submittingAdmin} className="btn-danger">
              {submittingAdmin && <Loader2 className="w-4 h-4 animate-spin" />} Delete
            </button>
          </>
        }
      >
        <p className="text-sm text-text-secondary">
          Are you sure you want to delete admin <span className="font-semibold text-text-primary">{adminDeleteTarget?.username}</span>?
          This action cannot be undone.
        </p>
      </Modal>

      {/* Change Role Modal */}
      <Modal isOpen={!!roleUpdateTarget} onClose={() => setRoleUpdateTarget(null)} title="Update User Role" size="sm">
        <div className="space-y-4">
          <p className="text-sm text-text-secondary mb-4">
            Change role for user <span className="font-semibold text-text-primary">{roleUpdateTarget?.first_name}</span>
          </p>
          <select value={newRole} onChange={(e) => setNewRole(e.target.value)} className="input-field cursor-pointer">
            <option value="USER">User (Standard)</option>
            <option value="STAFF">Staff (Can add content)</option>
            <option value="ADMIN">Admin (Can manage users/bot)</option>
            <option value="OWNER">Owner (Full access)</option>
          </select>
          <div className="pt-4 flex justify-end gap-3 border-t border-border mt-6">
            <button type="button" onClick={() => setRoleUpdateTarget(null)} className="btn-secondary">Cancel</button>
            <button onClick={handleUpdateRole} className="btn-primary" disabled={submittingRole}>
              {submittingRole ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Role'}
            </button>
          </div>
        </div>
      </Modal>

    </div>
  );
}
