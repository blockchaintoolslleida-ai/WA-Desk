const STATUS_COLORS = {
  connected: { bg: '#DCFCE7', text: '#166534', dot: '#22C55E' },
  verified: { bg: '#DCFCE7', text: '#166534', dot: '#22C55E' },
  valid: { bg: '#DCFCE7', text: '#166534', dot: '#22C55E' },
  disconnected: { bg: '#FEE2E2', text: '#991B1B', dot: '#EF4444' },
  error: { bg: '#FEE2E2', text: '#991B1B', dot: '#EF4444' },
  expired: { bg: '#FEF3C7', text: '#92400E', dot: '#F59E0B' },
  not_configured: { bg: '#F1F5F9', text: '#475569', dot: '#94A3B8' },
  not_set: { bg: '#F1F5F9', text: '#475569', dot: '#94A3B8' },
};

export default function StatusBadge({ status, t }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.not_set;
  return (
    <span data-testid={`status-${status}`} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold"
      style={{ background: c.bg, color: c.text }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.dot }} />
      {t(`admin.status.${status}`)}
    </span>
  );
}
