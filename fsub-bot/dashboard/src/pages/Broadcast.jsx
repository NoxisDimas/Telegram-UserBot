import { useState } from 'react';
import { Send, Type, Image, Video, Loader2, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api/client';
import Modal from '../components/Modal';

const messageTypes = [
  { value: 'text', label: 'Text', icon: Type },
  { value: 'photo', label: 'Photo', icon: Image },
  { value: 'video', label: 'Video', icon: Video },
];

export default function Broadcast() {
  const [form, setForm] = useState({ message_type: 'text', text: '', media_url: '' });
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = () => {
    if (!form.text && form.message_type === 'text') return toast.error('Please enter a message');
    if (form.message_type !== 'text' && !form.media_url) return toast.error('Please enter a media URL or file ID');
    setShowConfirm(true);
  };

  const handleBroadcast = async () => {
    setSubmitting(true);
    try {
      const payload = {
        message_type: form.message_type,
        ...(form.text && { text: form.text }),
        ...(form.media_url && { media_url: form.media_url }),
      };
      await api.post('/broadcast/', payload);
      toast.success('Broadcast queued successfully!');
      setShowConfirm(false);
      setForm({ message_type: 'text', text: '', media_url: '' });
    } catch (err) { toast.error(err.response?.data?.detail || 'Broadcast failed'); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">Broadcast Message</h1>
        <p className="text-sm text-text-muted mt-1.5">Send a message to all bot users</p>
      </div>

      <div className="card overflow-hidden">
        <div className="p-6 lg:p-8 space-y-6">
          {/* Type selector */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-3">Message Type</label>
            <div className="grid grid-cols-3 gap-3">
              {messageTypes.map(({ value, label, icon: Icon }) => (
                <button key={value} type="button" onClick={() => setForm({ ...form, message_type: value })}
                  className={`flex items-center justify-center gap-2.5 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 border cursor-pointer ${
                    form.message_type === value
                      ? 'bg-neon/8 text-neon border-neon/25 neon-glow-sm'
                      : 'bg-bg-secondary text-text-muted border-border hover:border-border-hover hover:text-text-primary'
                  }`}>
                  <Icon className="w-4 h-4" /> {label}
                </button>
              ))}
            </div>
          </div>

          {/* Text */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-text-secondary">
                {form.message_type === 'text' ? 'Message' : 'Caption'}
                {form.message_type === 'text' && <span className="text-danger ml-0.5">*</span>}
              </label>
              <span className="text-xs text-text-muted">{form.text.length} chars</span>
            </div>
            <textarea value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })}
              placeholder={form.message_type === 'text' ? 'Enter your broadcast message...' : 'Enter caption (optional)...'}
              rows={6} className="input-field resize-none" />
          </div>

          {/* Media URL */}
          {form.message_type !== 'text' && (
            <div className="animate-slide-up">
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Media URL / File ID <span className="text-danger">*</span>
              </label>
              <input type="text" value={form.media_url}
                onChange={(e) => setForm({ ...form, media_url: e.target.value })}
                placeholder="Enter Telegram file_id or URL" className="input-field" />
              <p className="text-xs text-text-muted mt-2">You can use a Telegram file_id or a publicly accessible URL</p>
            </div>
          )}

          {/* Preview */}
          {form.text && (
            <div className="animate-fade-in">
              <label className="block text-sm font-medium text-text-secondary mb-2">Preview</label>
              <div className="p-5 bg-bg-secondary border border-border rounded-xl">
                <p className="text-sm text-text-primary whitespace-pre-wrap break-words leading-relaxed">{form.text}</p>
                {form.media_url && (
                  <p className="text-xs text-text-muted mt-3">📎 {form.message_type === 'photo' ? 'Photo' : 'Video'} attached</p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 lg:px-8 py-5 bg-bg-secondary/30 border-t border-border">
          <button onClick={handleSubmit} className="btn-primary">
            <Send className="w-4 h-4" /> Send Broadcast
          </button>
        </div>
      </div>

      {/* Confirm Modal */}
      <Modal isOpen={showConfirm} onClose={() => setShowConfirm(false)} title="Confirm Broadcast" size="sm"
        footer={
          <>
            <button onClick={() => setShowConfirm(false)} className="btn-secondary">Cancel</button>
            <button onClick={handleBroadcast} disabled={submitting} className="btn-primary">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />} Confirm & Send
            </button>
          </>
        }
      >
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl bg-warning/10 border border-warning/20 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-warning" />
          </div>
          <div>
            <p className="text-sm text-text-secondary leading-relaxed">
              This will send a <span className="font-semibold text-text-primary">{form.message_type}</span> message to <span className="font-semibold text-text-primary">all users</span>.
            </p>
            <p className="text-xs text-text-muted mt-2">This action cannot be undone. Are you sure?</p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
