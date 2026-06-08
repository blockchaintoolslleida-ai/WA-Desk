import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

// Format date to locale string
export function formatDate(date, options = {}) {
  if (!date) return '-';
  const d = new Date(date);
  return d.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...options
  });
}

// Format datetime to locale string
export function formatDateTime(date, options = {}) {
  if (!date) return '-';
  const d = new Date(date);
  return d.toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...options
  });
}

// Format relative time (e.g., "hace 2 horas")
export function formatRelativeTime(date) {
  if (!date) return '-';
  const now = new Date();
  const d = new Date(date);
  const diff = now - d;
  
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  
  if (minutes < 1) return 'Ara mateix';
  if (minutes < 60) return `Fa ${minutes} min`;
  if (hours < 24) return `Fa ${hours}h`;
  if (days < 7) return `Fa ${days} dies`;
  
  return formatDate(date);
}

// Get status label
export function getStatusLabel(status) {
  const labels = {
    new: 'Nou',
    pending_identification: 'Pendent identificació',
    waiting_customer: 'Esperant client',
    identified: 'Identificat',
    quoted: 'Pressupostat',
    waiting_internal: 'Esperant intern',
    resolved: 'Resolt',
    closed: 'Tancat',
    reopened: 'Reobert'
  };
  return labels[status] || status;
}

// Get priority label
export function getPriorityLabel(priority) {
  const labels = {
    low: 'Baixa',
    normal: 'Normal',
    high: 'Alta',
    urgent: 'Urgent'
  };
  return labels[priority] || priority;
}

// Get channel label
export function getChannelLabel(channel) {
  const labels = {
    whatsapp: 'WhatsApp',
    portal: 'Portal',
    email: 'Email',
    web_form: 'Formulari web',
    internal: 'Intern'
  };
  return labels[channel] || channel;
}

// Get role label
export function getRoleLabel(role) {
  const labels = {
    super_admin: 'Super Admin',
    tenant_admin: 'Administrador',
    supervisor: 'Supervisor',
    agent: 'Agent',
    customer: 'Client'
  };
  return labels[role] || role;
}

// Format phone number
export function formatPhone(phone) {
  if (!phone) return '-';
  // Remove all non-digits
  const digits = phone.replace(/\D/g, '');
  
  // Format Spanish phone number
  if (digits.startsWith('34') && digits.length === 11) {
    return `+34 ${digits.slice(2, 5)} ${digits.slice(5, 8)} ${digits.slice(8)}`;
  }
  
  return phone;
}

// Calculate SLA status
export function getSLAStatus(slaDueAt, status) {
  if (!slaDueAt) return null;
  if (['resolved', 'closed'].includes(status)) return 'completed';
  
  const now = new Date();
  const due = new Date(slaDueAt);
  const diff = due - now;
  
  if (diff < 0) return 'breached';
  if (diff < 3600000) return 'critical'; // Less than 1 hour
  if (diff < 7200000) return 'warning'; // Less than 2 hours
  return 'ok';
}

// Format time remaining for SLA
export function formatSLARemaining(slaDueAt) {
  if (!slaDueAt) return '-';
  
  const now = new Date();
  const due = new Date(slaDueAt);
  const diff = due - now;
  
  if (diff < 0) {
    const hours = Math.abs(Math.floor(diff / 3600000));
    return `Vençut fa ${hours}h`;
  }
  
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  
  return `${hours}h ${minutes}m`;
}

// Get confidence level
export function getConfidenceLevel(score) {
  if (score >= 0.8) return 'high';
  if (score >= 0.5) return 'medium';
  return 'low';
}

// Format confidence score
export function formatConfidence(score) {
  if (score === null || score === undefined) return '-';
  return `${Math.round(score * 100)}%`;
}

// Get stock status
export function getStockStatus(available) {
  if (available > 10) return 'available';
  if (available > 0) return 'low';
  return 'out';
}

// Truncate text
export function truncate(text, length = 50) {
  if (!text) return '';
  if (text.length <= length) return text;
  return text.substring(0, length) + '...';
}

// Generate initials from name
export function getInitials(name) {
  if (!name) return '??';
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .toUpperCase()
    .substring(0, 2);
}
