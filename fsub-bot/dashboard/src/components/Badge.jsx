const variants = {
  success: 'bg-neon-glow-soft text-neon border border-border-neon',
  danger: 'bg-danger-dim text-danger border border-danger/20',
  warning: 'bg-warning/10 text-warning border border-warning/20',
  neutral: 'bg-bg-secondary text-text-muted border border-border',
  info: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
};

export default function Badge({ children, variant = 'neutral', dot = false, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]} ${className}`}>
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full ${
          variant === 'success' ? 'bg-neon' :
          variant === 'danger' ? 'bg-danger' :
          variant === 'warning' ? 'bg-warning' :
          'bg-text-muted'
        }`} />
      )}
      {children}
    </span>
  );
}
