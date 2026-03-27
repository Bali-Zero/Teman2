'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Moon,
  Sun,
  Sparkles,
  PenTool,
  Search,
  Share2,
  Calendar,
  Plus,
  X,
  Command,
  Eye,
  EyeOff,
  Volume2,
  VolumeX,
  Twitter,
  Linkedin,
  Instagram,
  Clock,
  TrendingUp,
  FileText,
  Quote,
  Link,
  Trash2,
  Copy,
  Wand2,
  Hash,
  ChevronDown,
  ChevronRight,
  GripVertical,
  ExternalLink,
  Bookmark,
  Image,
  Palette,
  Type,
  Shuffle,
  Zap,
  Target,
  BarChart3,
  CheckCircle2,
  Send,
  Play,
  Pause,
  RefreshCw,
  ListOrdered,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  List,
  Heading1,
  Heading2,
  Code,
  ImageIcon,
  LinkIcon,
  MoreHorizontal,
  ArrowRight,
  Star,
  Heart,
  MessageCircle,
  Repeat2,
  BookOpen,
  Video,
  Music,
  CloudRain,
  Coffee,
  Layers,
  Settings,
  Save,
  LucideIcon,
  Maximize2,
} from 'lucide-react';
import { dreamApi } from '@/lib/api/dream.api';
import { logger } from '@/lib/logger';

// ============ TYPES ============
interface ArticleVersion {
  id: number;
  timestamp: string;
  content: string;
}

interface Article {
  id: number;
  title: string;
  content: string;
  outline: string[];
  wordCount: number;
  seoScore: number;
  createdAt: string;
  versions: ArticleVersion[];
}

interface Inspiration {
  id: number;
  type: 'color' | 'quote' | 'prompt';
  value?: string;
  name?: string;
  source?: string;
  content?: string;
  author?: string;
}

interface InstagramSlide {
  slide: number;
  content: string;
  subtitle: string;
}

interface SocialPosts {
  twitter: string | string[];
  linkedin: string;
  instagram: InstagramSlide[];
  tiktok: string;
  newsletter: string;
}

interface CalendarEvent {
  id: number;
  date: string;
  title: string;
  platform: string;
  status: 'draft' | 'scheduled';
}

interface SwipeFile {
  id: number;
  title: string;
  url: string;
  category: string;
}

interface QueueItem {
  id: number;
  type: string;
  status: string;
  scheduledFor?: string;
}

interface StoreState {
  activeZone: 'inspiration' | 'composer' | 'research' | 'social' | 'publish';
  focusMode: boolean;
  ambientSound: string;
  isPlaying: boolean;
  articles: Article[];
  currentArticleId: number;
  inspirations: Inspiration[];
  swipeFiles: SwipeFile[];
  socialPosts: SocialPosts;
  calendarEvents: CalendarEvent[];
  queue: QueueItem[];
}

// ============ ZUSTAND-LIKE STATE STORE ============
type Listener<T> = (state: T) => void;

const createStore = <T,>(initialState: T) => {
  let state = initialState;
  const listeners = new Set<Listener<T>>();

  return {
    getState: () => state,
    setState: (partial: Partial<T> | ((state: T) => Partial<T>)) => {
      state =
        typeof partial === 'function' ? { ...state, ...partial(state) } : { ...state, ...partial };
      listeners.forEach((l) => l(state));
    },
    subscribe: (listener: Listener<T>) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
};

const useStore = <T, R = T>(
  store: ReturnType<typeof createStore<T>>,
  selector: (s: T) => R = (s: T) => s as unknown as R
) => {
  const [state, setState] = useState(() => selector(store.getState()));
  useEffect(() => {
    return store.subscribe((newState) => {
      const selected = selector(newState);
      setState(selected);
    });
  }, [store, selector]);
  return state;
};

// Initialize store with localStorage persistence
const loadFromStorage = (): StoreState | null => {
  if (typeof window === 'undefined') return null;
  try {
    const saved = localStorage.getItem('dreamThinkingRoom');
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
};

const initialState: StoreState = loadFromStorage() || {
  activeZone: 'composer',
  focusMode: false,
  ambientSound: 'silence',
  isPlaying: false,
  articles: [
    {
      id: 1,
      title: "Come l'AI sta trasformando il Content Marketing",
      content:
        "<p>L'intelligenza artificiale sta rivoluzionando il modo in cui creiamo contenuti...</p><p>In questo articolo esploreremo le principali tendenze e come sfruttarle per la tua strategia.</p>",
      outline: ['Introduzione', 'Trend AI nel marketing', 'Case studies', 'Conclusioni'],
      wordCount: 342,
      seoScore: 78,
      createdAt: new Date().toISOString(),
      versions: [],
    },
  ],
  currentArticleId: 1,
  inspirations: [
    { id: 1, type: 'color', value: '#8b5cf6', name: 'Viola brand' },
    { id: 2, type: 'color', value: '#ec4899', name: 'Rosa accent' },
    {
      id: 3,
      type: 'quote',
      value: 'Content is king, but distribution is queen.',
      source: 'Gary Vee',
    },
  ],
  swipeFiles: [],
  socialPosts: {
    twitter: '',
    linkedin: '',
    instagram: [],
    tiktok: '',
    newsletter: '',
  },
  calendarEvents: [
    {
      id: 1,
      date: '2026-02-03',
      title: 'Blog: AI Marketing',
      platform: 'blog',
      status: 'draft',
    },
    {
      id: 2,
      date: '2026-02-05',
      title: 'Thread Twitter',
      platform: 'twitter',
      status: 'scheduled',
    },
    {
      id: 3,
      date: '2026-02-07',
      title: 'LinkedIn Post',
      platform: 'linkedin',
      status: 'scheduled',
    },
  ],
  queue: [],
};

const store = createStore<StoreState>(initialState);

// Save to localStorage on state change
const StoreSubscriber = () => {
  useEffect(() => {
    return store.subscribe((state) => {
      localStorage.setItem('dreamThinkingRoom', JSON.stringify(state));
    });
  }, []);
  return null;
};

// ============ COMPONENTS STUB ============

// ============ PARTICLE SYSTEM ============
interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  alpha: number;
}

const ParticleCanvas = ({ active }: { active: boolean }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Particle[]>([]);
  const mouseRef = useRef({ x: 0, y: 0 });
  const animationRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!active || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Initialize particles
    particlesRef.current = [];
    for (let i = 0; i < 50; i++) {
      particlesRef.current.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 3 + 1,
        alpha: Math.random() * 0.5 + 0.2,
      });
    }

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particlesRef.current.forEach((p) => {
        // Move towards mouse slightly
        const dx = mouseRef.current.x - p.x;
        const dy = mouseRef.current.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 150) {
          p.vx += dx * 0.0001;
          p.vy += dy * 0.0001;
        }

        p.x += p.vx;
        p.y += p.vy;

        // Bounce off edges
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        // Draw particle
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
        gradient.addColorStop(0, `rgba(139, 92, 246, ${p.alpha})`);
        gradient.addColorStop(1, `rgba(236, 72, 153, 0)`);

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      });

      animationRef.current = requestAnimationFrame(animate);
    };
    animate();

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    // @ts-ignore - native event typing
    canvas.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('resize', resize);
      // @ts-ignore
      canvas.removeEventListener('mousemove', handleMouseMove);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [active]);

  if (!active) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-auto"
      style={{ opacity: 0.6 }}
    />
  );
};

// ============ CONFETTI EFFECT ============
interface ConfettiParticle {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  rotation: number;
}

const Confetti = ({ trigger }: { trigger: boolean }) => {
  const [particles, setParticles] = useState<ConfettiParticle[]>([]);

  useEffect(() => {
    if (!trigger) return;

    const newParticles = Array.from({ length: 50 }, (_, i) => ({
      id: i,
      x: 50 + Math.random() * 10 - 5,
      y: 50,
      vx: (Math.random() - 0.5) * 20,
      vy: -Math.random() * 15 - 5,
      color: ['#8b5cf6', '#ec4899', '#fbbf24', '#34d399', '#60a5fa'][Math.floor(Math.random() * 5)],
      rotation: Math.random() * 360,
    }));

    setParticles(newParticles);
    setTimeout(() => setParticles([]), 3000);
  }, [trigger]);

  if (particles.length === 0) return null;

  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute w-3 h-3 animate-confetti"
          style={
            {
              left: `${p.x}%`,
              top: `${p.y}%`,
              backgroundColor: p.color,
              transform: `rotate(${p.rotation}deg)`,
              animation: `confetti 3s ease-out forwards`,
              '--vx': p.vx,
              '--vy': p.vy,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
};

// ============ TYPING EFFECT ============
const TypingText = ({
  text,
  speed = 30,
  onComplete,
}: {
  text: string;
  speed?: number;
  onComplete?: () => void;
}) => {
  const [displayed, setDisplayed] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    setDisplayed('');
    setIsComplete(false);
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
        setIsComplete(true);
        onComplete?.();
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {!isComplete && <span className="animate-pulse">|</span>}
    </span>
  );
};

// ============ GLASS CARD COMPONENT ============
const GlassCard = ({
  children,
  className = '',
  glow = false,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  onClick?: () => void;
}) => (
  <div
    onClick={onClick}
    className={`
      relative backdrop-blur-xl bg-white/5
      border border-white/10 rounded-2xl
      ${glow ? 'shadow-lg shadow-violet-500/20' : ''}
      transition-all duration-300 hover:bg-white/10 hover:border-white/20
      ${className}
    `}
  >
    {children}
  </div>
);

// ============ ZONE NAVIGATION ============
const zones: {
  id: StoreState['activeZone'];
  icon: LucideIcon;
  label: string;
  color: string;
}[] = [
  {
    id: 'inspiration',
    icon: Moon,
    label: 'Inspiration',
    color: 'from-violet-500 to-indigo-500',
  },
  {
    id: 'composer',
    icon: PenTool,
    label: 'Composer',
    color: 'from-pink-500 to-rose-500',
  },
  {
    id: 'research',
    icon: Search,
    label: 'Research',
    color: 'from-cyan-500 to-blue-500',
  },
  {
    id: 'social',
    icon: Share2,
    label: 'Social',
    color: 'from-amber-500 to-orange-500',
  },
  {
    id: 'publish',
    icon: Calendar,
    label: 'Publish',
    color: 'from-emerald-500 to-teal-500',
  },
];

const ZoneNav = () => {
  const activeZone = useStore(store, (s) => s.activeZone);
  const focusMode = useStore(store, (s) => s.focusMode);

  if (focusMode) return null;

  return (
    <nav className="fixed left-4 top-1/2 -translate-y-1/2 z-40 flex flex-col gap-2">
      {zones.map((zone) => {
        const Icon = zone.icon;
        const isActive = activeZone === zone.id;
        return (
          <button
            key={zone.id}
            onClick={() => store.setState({ activeZone: zone.id })}
            className={`
              group relative p-3 rounded-xl transition-all duration-300
              ${
                isActive
                  ? `bg-gradient-to-r ${zone.color} shadow-lg`
                  : 'bg-white/5 hover:bg-white/10'
              }
            `}
          >
            <Icon size={20} className={isActive ? 'text-white' : 'text-zinc-400'} />
            <span
              className={`
              absolute left-full ml-3 px-3 py-1.5 rounded-lg text-sm font-medium
              bg-zinc-900 text-white whitespace-nowrap
              opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0
              transition-all duration-200 pointer-events-none
            `}
            >
              {zone.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
};

// ============ TOP BAR ============
const TopBar = () => {
  const focusMode = useStore(store, (s) => s.focusMode);
  const ambientSound = useStore(store, (s) => s.ambientSound);
  const isPlaying = useStore(store, (s) => s.isPlaying);
  const [showSounds, setShowSounds] = useState(false);

  const sounds = [
    { id: 'silence', icon: VolumeX, label: 'Silenzio' },
    { id: 'lofi', icon: Music, label: 'Lo-Fi Beats' },
    { id: 'rain', icon: CloudRain, label: 'Pioggia' },
    { id: 'cafe', icon: Coffee, label: 'Caffetteria' },
  ];

  const currentSound = sounds.find((s) => s.id === ambientSound);
  const SoundIcon = currentSound?.icon || VolumeX;

  return (
    <header
      className={`
      fixed top-0 left-0 right-0 z-50 px-6 py-4
      flex items-center justify-between
      bg-gradient-to-b from-[#0a0a0f] to-transparent
      transition-opacity duration-500
      ${focusMode ? 'opacity-0 pointer-events-none' : 'opacity-100'}
    `}
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center">
          <Sparkles size={20} className="text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white">Dream Thinking Room</h1>
          <p className="text-xs text-zinc-500">Content creation studio</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Ambient Sound */}
        <div className="relative">
          <button
            onClick={() => setShowSounds(!showSounds)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
          >
            <SoundIcon size={16} className="text-zinc-400" />
            <span className="text-sm text-zinc-400">{currentSound?.label}</span>
            {isPlaying && ambientSound !== 'silence' && (
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            )}
          </button>

          {showSounds && (
            <div className="absolute top-full right-0 mt-2 p-2 rounded-xl bg-zinc-900/95 backdrop-blur border border-white/10 min-w-[160px]">
              {sounds.map((sound) => {
                const Icon = sound.icon;
                return (
                  <button
                    key={sound.id}
                    onClick={() => {
                      store.setState({
                        ambientSound: sound.id,
                        isPlaying: sound.id !== 'silence',
                      });
                      setShowSounds(false);
                    }}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm
                      ${ambientSound === sound.id ? 'bg-violet-500/20 text-violet-300' : 'text-zinc-400 hover:bg-white/5'}
                    `}
                  >
                    <Icon size={16} />
                    {sound.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Focus Mode */}
        <button
          onClick={() =>
            store.setState((s: StoreState) => ({
              ...s,
              focusMode: !s.focusMode,
            }))
          }
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
        >
          {focusMode ? <EyeOff size={16} /> : <Eye size={16} />}
          <span className="text-sm text-zinc-400">Focus</span>
        </button>

        {/* Command Palette Hint */}
        <div className="flex items-center gap-1 px-3 py-2 rounded-lg bg-white/5">
          <Command size={14} className="text-zinc-500" />
          <span className="text-xs text-zinc-500">K</span>
        </div>
      </div>
    </header>
  );
};

// ============ COMMAND PALETTE ============
const CommandPalette = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = [
    {
      id: 'new-article',
      label: 'Nuovo articolo',
      icon: FileText,
      action: () => {},
    },
    {
      id: 'focus',
      label: 'Toggle Focus Mode',
      icon: Eye,
      action: () => store.setState((s: StoreState) => ({ ...s, focusMode: !s.focusMode })),
    },
    {
      id: 'inspiration',
      label: 'Vai a Inspiration',
      icon: Moon,
      action: () => store.setState({ activeZone: 'inspiration' }),
    },
    {
      id: 'composer',
      label: 'Vai a Composer',
      icon: PenTool,
      action: () => store.setState({ activeZone: 'composer' }),
    },
    {
      id: 'social',
      label: 'Vai a Social',
      icon: Share2,
      action: () => store.setState({ activeZone: 'social' }),
    },
    {
      id: 'publish',
      label: 'Vai a Publish',
      icon: Calendar,
      action: () => store.setState({ activeZone: 'publish' }),
    },
    { id: 'spark', label: 'Random Spark', icon: Zap, action: () => {} },
  ];

  const filtered = commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
      setQuery('');
    }
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg mx-4" onClick={(e) => e.stopPropagation()}>
        <GlassCard className="overflow-hidden" glow>
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
            <Search size={18} className="text-zinc-500" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Cerca comandi..."
              className="flex-1 bg-transparent text-white placeholder-zinc-500 outline-none"
            />
            <kbd className="px-2 py-1 text-xs text-zinc-500 bg-white/5 rounded">ESC</kbd>
          </div>
          <div className="max-h-80 overflow-auto p-2">
            {filtered.map((cmd) => {
              const Icon = cmd.icon;
              return (
                <button
                  key={cmd.id}
                  onClick={() => {
                    cmd.action();
                    onClose();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-white/10 transition-colors group"
                >
                  <Icon size={18} className="text-zinc-400 group-hover:text-violet-400" />
                  <span className="text-sm text-zinc-300">{cmd.label}</span>
                </button>
              );
            })}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

// ============ INSPIRATION CORNER ============
const InspirationCorner = () => {
  const inspirations = useStore(store, (s) => s.inspirations);
  const [randomSpark, setRandomSpark] = useState<Inspiration | null>(null);

  const generateSpark = () => {
    const sparks: Inspiration[] = [
      {
        id: 101,
        type: 'prompt',
        content: 'Come cambierebbe il tuo settore tra 50 anni?',
      },
      {
        id: 102,
        type: 'prompt',
        content: 'Scrivi una lettera al tuo cliente ideale di domani.',
      },
      {
        id: 103,
        type: 'quote',
        content: 'Creativity is intelligence having fun.',
        author: 'Albert Einstein',
      },
    ];
    setRandomSpark(sparks[Math.floor(Math.random() * sparks.length)]);
  };

  return (
    <div className="relative h-full p-6 overflow-auto">
      <ParticleCanvas active={true} />

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Mood Board */}
        <GlassCard className="p-5 overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-500/10 to-pink-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
            <Palette size={20} className="text-pink-400" />
            Mood Board & Palette
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {inspirations
              .filter((i) => i.type === 'color')
              .map((color) => (
                <div key={color.id} className="space-y-2 group/color cursor-pointer">
                  <div
                    className="aspect-square rounded-xl shadow-lg transition-transform hover:scale-105 hover:rotate-3"
                    style={{ backgroundColor: color.value }}
                  />
                  <p className="text-xs text-center text-zinc-400 opacity-0 group-hover/color:opacity-100 transition-opacity">
                    {color.name}
                  </p>
                </div>
              ))}
            <button className="aspect-square rounded-xl border-2 border-dashed border-white/10 flex items-center justify-center hover:border-white/20 hover:bg-white/5 transition-all">
              <Plus size={24} className="text-zinc-500" />
            </button>
          </div>
        </GlassCard>

        {/* Random Spark */}
        <GlassCard className="p-5 flex flex-col justify-center text-center" glow>
          <div className="mb-4 flex justify-center">
            <div className="p-3 rounded-full bg-amber-500/20 text-amber-400 animate-pulse">
              <Zap size={24} />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Random Spark</h3>
          <div className="min-h-[80px] flex items-center justify-center">
            {randomSpark ? (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
                <p className="text-lg text-zinc-200 font-medium leading-relaxed">
                  "{randomSpark.content}"
                </p>
                {randomSpark.author && (
                  <p className="text-sm text-zinc-500 mt-2">— {randomSpark.author}</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Clicca per generare una scintilla creativa</p>
            )}
          </div>
          <button
            onClick={generateSpark}
            className="mt-6 mx-auto flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors"
          >
            <Shuffle size={16} />
            Genera Nuova
          </button>
        </GlassCard>

        {/* Trend Radar */}
        <GlassCard className="p-5 lg:col-span-2">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
            <TrendingUp size={20} className="text-cyan-400" />
            Trend Radar
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['AI Generativa', 'Micro-Community', 'Video Short-form'].map((trend, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:border-cyan-500/30 transition-colors cursor-pointer"
              >
                <span className="text-zinc-300">{trend}</span>
                <div className="flex items-center gap-1 text-xs text-emerald-400">
                  <TrendingUp size={12} />+{15 + i * 5}%
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

// ============ ARTICLE COMPOSER ============
const ArticleComposer = () => {
  const articles = useStore(store, (s) => s.articles);
  const currentId = useStore(store, (s) => s.currentArticleId);
  const article = articles.find((a) => a.id === currentId) || articles[0];

  const [title, setTitle] = useState(article.title);
  const [content, setContent] = useState(article.content);
  const [outline, setOutline] = useState(article.outline);
  const [isAIGenerating, setIsAIGenerating] = useState(false);
  const [showAIPanel, setShowAIPanel] = useState(true);
  const [aiOutput, setAiOutput] = useState('');

  const editorRef = useRef<HTMLDivElement>(null);

  // Auto-save to Backend (Debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      // Save local first
      const newState = {
        ...store.getState(),
        articles: store
          .getState()
          .articles.map((a) => (a.id === currentId ? { ...a, title, content, outline } : a)),
      };
      store.setState(newState);

      // Persist to backend
      dreamApi
        .saveState('current-user', newState)
        .then(() => {
          // Cloud save successful - logged by analytics service
        })
        .catch((err) => logger.error('Save failed', {}, err as Error));
    }, 2000);
    return () => clearTimeout(timer);
  }, [title, content, outline, currentId]); // Added dependencies to ensure latest state is captured

  const seoScore = Math.min(100, Math.floor((content.length / 500) * 100));

  const runAIAction = async (action: string) => {
    setIsAIGenerating(true);
    setAiOutput('');

    try {
      // Real API Call
      const res = await dreamApi.generate({
        prompt: content,
        mode: action as any,
        context: title,
      });

      if (res.success) {
        setAiOutput(res.text);
      } else {
        setAiOutput('Errore nella generazione. Riprova.');
      }
    } catch (e) {
      logger.error('AI generation failed', {}, e as Error);
      setAiOutput('Errore di connessione.');
    } finally {
      setIsAIGenerating(false);
    }
  };

  const aiActions = [
    { id: 'expand', label: 'Espandi concetto', icon: Maximize2 },
    { id: 'rewrite', label: 'Riscrivi meglio', icon: RefreshCw },
    { id: 'tone', label: 'Cambia tono', icon: Wand2 },
  ];

  return (
    <div className="h-full flex">
      {/* Main Editor */}
      <div className="flex-1 flex flex-col p-6 overflow-auto">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="bg-transparent text-4xl font-bold text-white placeholder-zinc-600 outline-none mb-6"
          placeholder="Titolo dell'articolo..."
        />

        {/* Toolbar */}
        <div className="flex items-center gap-1 mb-4 p-2 rounded-xl bg-white/5 w-fit border border-white/10 sticky top-0 z-20 backdrop-blur-md">
          {[
            Bold,
            Italic,
            Underline,
            null,
            AlignLeft,
            List,
            ListOrdered,
            null,
            LinkIcon,
            ImageIcon,
            Code,
          ].map((Icon, i) =>
            Icon ? (
              <button
                key={i}
                className="p-2 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
              >
                <Icon size={18} />
              </button>
            ) : (
              <div key={i} className="w-px h-6 bg-white/10 mx-1" />
            )
          )}
        </div>

        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          className="flex-1 outline-none text-lg text-zinc-300 leading-relaxed max-w-3xl prose prose-invert"
          dangerouslySetInnerHTML={{ __html: content }}
          onBlur={(e) => setContent(e.currentTarget.innerHTML)}
        />
      </div>

      {/* Right Sidebar */}
      <div className="w-80 border-l border-white/10 p-4 space-y-4 overflow-auto bg-[#0a0a0f]/50 backdrop-blur-sm">
        {/* AI Assist Panel */}
        {showAIPanel && (
          <GlassCard className="p-4" glow>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
              <Wand2 size={16} className="text-violet-400" />
              AI Assist
            </h3>

            <div className="space-y-2 mb-4">
              {aiActions.map((action) => (
                <button
                  key={action.id}
                  onClick={() => runAIAction(action.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-300 bg-white/5 hover:bg-white/10 transition-colors text-left"
                >
                  <action.icon size={14} className="text-violet-400" />
                  {action.label}
                </button>
              ))}
            </div>

            {(isAIGenerating || aiOutput) && (
              <div className="p-3 rounded-lg bg-white/5 border border-violet-500/30">
                {isAIGenerating ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-400">
                    <RefreshCw size={14} className="animate-spin" />
                    Generando...
                  </div>
                ) : (
                  <div className="text-sm text-zinc-300 whitespace-pre-wrap">
                    <TypingText text={aiOutput} speed={10} />
                  </div>
                )}
              </div>
            )}
          </GlassCard>
        )}

        {/* Outline Builder */}
        <GlassCard className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
              <Layers size={16} className="text-cyan-400" />
              Outline
            </h3>
            <button
              onClick={() => setOutline([...outline, 'Nuova sezione'])}
              className="p-1 rounded hover:bg-white/10"
            >
              <Plus size={14} className="text-zinc-400" />
            </button>
          </div>

          <div className="space-y-1">
            {outline.map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-2 p-2 rounded-lg hover:bg-white/5 group cursor-move"
              >
                <GripVertical size={14} className="text-zinc-600" />
                <span className="flex-1 text-sm text-zinc-300">{item}</span>
                <button
                  onClick={() => setOutline(outline.filter((_, j) => j !== i))}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10"
                >
                  <X size={12} className="text-zinc-500" />
                </button>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* SEO Sidebar */}
        <GlassCard className="p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <BarChart3 size={16} className="text-emerald-400" />
            SEO Score
          </h3>

          <div className="flex items-center gap-4 mb-4">
            <div className="relative w-16 h-16">
              <svg className="w-full h-full -rotate-90">
                <circle
                  cx="32"
                  cy="32"
                  r="28"
                  fill="none"
                  stroke="rgba(255,255,255,0.1)"
                  strokeWidth="6"
                />
                <circle
                  cx="32"
                  cy="32"
                  r="28"
                  fill="none"
                  stroke="url(#seoGradient)"
                  strokeWidth="6"
                  strokeDasharray={`${seoScore * 1.76} 176`}
                  strokeLinecap="round"
                />
                <defs>
                  <linearGradient id="seoGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#ec4899" />
                  </linearGradient>
                </defs>
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-white">
                {seoScore}
              </span>
            </div>
            <div className="flex-1">
              <p className="text-sm text-zinc-400">
                {seoScore >= 80 ? 'Ottimo!' : seoScore >= 50 ? 'Buono' : 'Migliorabile'}
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

// ============ RESEARCH SCRAPER ============
const ResearchScraper = () => {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [scrapedData, setScrapedData] = useState<{
    title: string;
    keyPoints: string[];
    quotes: { text: string; author: string }[];
  } | null>(null);

  const handleScrape = async () => {
    if (!url) return;
    setIsLoading(true);
    try {
      const res = await dreamApi.scrape(url);
      if (res.success) {
        setScrapedData({
          title: res.title,
          keyPoints: res.keyPoints,
          quotes: res.quotes,
        });
      }
    } catch (e) {
      logger.error('Scrape failed', {}, e as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const competitors = [
    { name: 'HubSpot Blog', url: 'hubspot.com', status: 'active' },
    {
      name: 'Content Marketing Institute',
      url: 'contentmarketinginstitute.com',
      status: 'active',
    },
    { name: 'Copyblogger', url: 'copyblogger.com', status: 'paused' },
  ];

  const contentGaps = [
    { topic: 'AI Video Generation', difficulty: 'medium', opportunity: 'high' },
    {
      topic: 'Voice Search Optimization',
      difficulty: 'easy',
      opportunity: 'medium',
    },
    { topic: 'Interactive Content', difficulty: 'hard', opportunity: 'high' },
  ];

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* URL Scraper */}
        <GlassCard className="p-5" glow>
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
            <Link size={20} className="text-cyan-400" />
            URL Scraper
          </h3>

          <div className="flex gap-2 mb-4">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Incolla URL da analizzare..."
              className="flex-1 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-white placeholder-zinc-500 outline-none focus:border-violet-500/50"
            />
            <button
              onClick={handleScrape}
              disabled={isLoading}
              className="px-4 py-2 rounded-xl bg-cyan-500 text-white font-medium hover:bg-cyan-600 transition-colors disabled:opacity-50"
            >
              {isLoading ? <RefreshCw size={18} className="animate-spin" /> : 'Analizza'}
            </button>
          </div>

          {scrapedData && (
            <div className="space-y-4">
              <div className="p-3 rounded-xl bg-white/5">
                <h4 className="text-sm font-medium text-white mb-1">{scrapedData.title}</h4>
                <p className="text-xs text-zinc-500">Estratto automaticamente</p>
              </div>

              <div>
                <h5 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">
                  Punti chiave
                </h5>
                <ul className="space-y-1">
                  {scrapedData.keyPoints.map((point, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                      <ChevronRight size={14} className="text-cyan-400 mt-0.5 flex-shrink-0" />
                      {point}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h5 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Citazioni</h5>
                {scrapedData.quotes.map((quote, i) => (
                  <div key={i} className="p-3 rounded-xl bg-white/5 border-l-2 border-cyan-500">
                    <p className="text-sm text-zinc-300 italic">"{quote.text}"</p>
                    <p className="text-xs text-zinc-500 mt-1">— {quote.author}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassCard>

        {/* Competitor Watch */}
        <GlassCard className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Eye size={20} className="text-pink-400" />
              Competitor Watch
            </h3>
            <button className="p-2 rounded-lg hover:bg-white/10">
              <Plus size={16} className="text-zinc-400" />
            </button>
          </div>

          <div className="space-y-2">
            {competitors.map((comp, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
                <div
                  className={`w-2 h-2 rounded-full ${comp.status === 'active' ? 'bg-emerald-400' : 'bg-zinc-600'}`}
                />
                <div className="flex-1">
                  <p className="text-sm text-white">{comp.name}</p>
                  <p className="text-xs text-zinc-500">{comp.url}</p>
                </div>
                <button className="p-2 rounded-lg hover:bg-white/10">
                  <ExternalLink size={14} className="text-zinc-400" />
                </button>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Content Gap Finder */}
        <GlassCard className="p-5 lg:col-span-2">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
            <Target size={20} className="text-amber-400" />
            Content Gap Finder
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {contentGaps.map((gap, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
              >
                <h4 className="text-white font-medium mb-2">{gap.topic}</h4>
                <div className="flex items-center gap-4 text-xs">
                  <span
                    className={`
                    px-2 py-1 rounded-full
                    ${
                      gap.difficulty === 'easy'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : gap.difficulty === 'medium'
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-red-500/20 text-red-400'
                    }
                  `}
                  >
                    {gap.difficulty}
                  </span>
                  <span
                    className={`
                    px-2 py-1 rounded-full
                    ${gap.opportunity === 'high' ? 'bg-violet-500/20 text-violet-400' : 'bg-zinc-500/20 text-zinc-400'}
                  `}
                  >
                    Opportunità: {gap.opportunity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Quote Collector */}
        <GlassCard className="p-5 lg:col-span-2">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
            <Quote size={20} className="text-violet-400" />
            Quote Collector
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-white/5">
              <p className="text-zinc-300 italic mb-2">
                "Content builds relationships. Relationships are built on trust. Trust drives
                revenue."
              </p>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">— Andrew Davis</span>
                <div className="flex gap-1">
                  <button className="p-1 rounded hover:bg-white/10">
                    <Copy size={14} className="text-zinc-500" />
                  </button>
                  <button className="p-1 rounded hover:bg-white/10">
                    <Trash2 size={14} className="text-zinc-500" />
                  </button>
                </div>
              </div>
            </div>

            <div className="border-2 border-dashed border-white/10 rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer hover:border-violet-500/50 transition-colors">
              <Quote size={24} className="text-zinc-600 mb-2" />
              <p className="text-sm text-zinc-500">Aggiungi citazione</p>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

// ============ SOCIAL TRANSFORMER ============
const SocialTransformer = () => {
  const [activeFormat, setActiveFormat] = useState('twitter');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generated, setGenerated] = useState<any>({}); // Using any for mock data structure flexibility

  const formats = [
    {
      id: 'twitter',
      label: 'Twitter/X Thread',
      icon: Twitter,
      color: 'text-sky-400',
    },
    {
      id: 'linkedin',
      label: 'LinkedIn Post',
      icon: Linkedin,
      color: 'text-blue-400',
    },
    {
      id: 'instagram',
      label: 'Instagram Carousel',
      icon: Instagram,
      color: 'text-pink-400',
    },
    {
      id: 'tiktok',
      label: 'TikTok Script',
      icon: Video,
      color: 'text-rose-400',
    },
    {
      id: 'newsletter',
      label: 'Newsletter Snippet',
      icon: BookOpen,
      color: 'text-emerald-400',
    },
  ];

  const mockContent = {
    twitter: [
      "Thread: L'AI sta cambiando il content marketing. Ecco cosa devi sapere per non restare indietro",
      "1/ Prima di tutto, l'AI non sostituisce la creatività umana. La potenzia.",
      '2/ Gli strumenti AI permettono di:\n- Analizzare trend in tempo reale\n- Generare varianti di copy\n- Personalizzare contenuti su scala',
      "3/ Ma attenzione: il tocco umano resta fondamentale. L'AI è un assistente, non un sostituto.",
      "4/ Il futuro appartiene a chi sa combinare:\n✨ Creatività umana\n🤖 Potenza dell'AI\n📊 Dati e analytics",
      'Se questo thread ti è stato utile, seguimi per altri contenuti sul marketing! 🚀',
    ],
    linkedin:
      "🚀 L'AI nel Content Marketing: Non è il Futuro, è il Presente\n\nHo passato gli ultimi 6 mesi a testare strumenti AI per la creazione di contenuti. Ecco cosa ho imparato:\n\n1️⃣ L'AI accelera, non sostituisce\nGli strumenti AI mi hanno permesso di ridurre del 40% il tempo di produzione, ma la strategia e la creatività restano umane.\n\n2️⃣ La personalizzazione è la chiave\nOggi possiamo creare contenuti personalizzati su scala, qualcosa impensabile solo 2 anni fa.\n\n3️⃣ Il dato guida tutto\nL'AI funziona meglio quando alimentata con dati di qualità. Investire in analytics è fondamentale.\n\n💡 Il mio consiglio: iniziate a sperimentare ora. Chi aspetta, resta indietro.\n\nQual è la vostra esperienza con l'AI nel marketing? Condividete nei commenti! 👇\n\n#ContentMarketing #AI #MarketingDigitale #Innovation",
    instagram: [
      {
        slide: 1,
        content: "L'AI sta cambiando il Content Marketing 🚀",
        subtitle: 'Swipe per scoprire come →',
      },
      {
        slide: 2,
        content: '40% in meno di tempo per creare contenuti',
        subtitle: 'Grazie agli strumenti AI',
      },
      {
        slide: 3,
        content: 'Personalizzazione su scala',
        subtitle: 'Contenuti unici per ogni audience',
      },
      {
        slide: 4,
        content: 'Ma il tocco umano resta fondamentale',
        subtitle: 'AI = Assistente, non sostituto',
      },
      {
        slide: 5,
        content: 'Inizia ora o resta indietro',
        subtitle: 'Salva questo post e seguimi! 💾',
      },
    ],
    tiktok:
      '🎬 HOOK (0-3 sec):\n"L\'AI ha cambiato tutto nel marketing. Ecco il segreto che nessuno ti dice."\n\n📱 BODY (3-45 sec):\n"Ok, ascolta. Ho testato tipo 20 tool AI negli ultimi mesi. E sai cosa? Il 90% sono inutili. Ma quel 10%... game changer totale.\n\nPrima ci mettevo 4 ore per un blog post. Ora? Un\'ora. Ma - e questo è importante - l\'AI non scrive per me. Mi aiuta a scrivere meglio.\n\nIl trucco? Usare l\'AI per le parti noiose: ricerca, outline, editing. La creatività? Quella resta tua."\n\n🎯 CTA (45-60 sec):\n"Vuoi sapere quali tool uso? Commenta \'AI\' e ti mando la lista. Segui per altri tips sul content marketing!"',
    newsletter:
      "📬 **Questa settimana in pillole**\n\nCiao!\n\nL'argomento caldo di questa settimana? L'AI nel content marketing.\n\nSo cosa stai pensando: \"Ancora?\" Ma aspetta, perché questa volta è diverso.\n\nHo passato l'ultimo mese a testare sul campo i nuovi strumenti. Il risultato? Un framework pratico che puoi applicare da subito.\n\n**I 3 insight chiave:**\n\n1. **L'AI accelera, non sostituisce** - Il tempo di produzione può calare del 40%, ma la strategia resta umana.\n\n2. **Qualità dei dati = Qualità dell'output** - Garbage in, garbage out. Prima di usare AI, sistema i tuoi dati.\n\n3. **Inizia piccolo** - Non serve rivoluzionare tutto. Parti da un task specifico e scala da lì.\n\n**La risorsa della settimana:**\n[Link al blog post completo]\n\nA presto,\n[Nome]",
  };

  const generateAll = async () => {
    setIsGenerating(true);
    // Trigger generation for all formats in parallel (mocking "all" for now by just doing one or simulating loop)
    // For MVP, we'll just demonstrate one real call or keep the mock for "ALL" heavy lift if backend is slow
    // Let's implement real call for the ACTIVE format at least, or just Mock for speed until bulk endpoint exists.
    // To respect the "Deep Integration" goal, let's use the generate API.

    try {
      // In a real scenario, we'd call a bulk endpoint.
      // Here we simulate it by calling generate for each
      const platforms = ['twitter', 'linkedin', 'instagram', 'tiktok', 'newsletter'];
      const results: Record<string, string | string[] | InstagramSlide[]> = {};

      await Promise.all(
        platforms.map(async (p) => {
          // This is heavy, maybe just do active? No, let's wow the user.
          // Actually, let's just do a specialized prompt for "social-pack"
          const res = await dreamApi.generate({
            prompt: 'Generate social media content for: ' + p,
            mode: 'expand', // Reusing mode param for now
            context: 'Social Media Pack',
          });
          if (res.success)
            results[p] = res.text; // Simple text mapping
          else results[p] = 'Error generating content';
        })
      );

      setGenerated(results);
    } catch (e) {
      logger.error('Content generation failed', {}, e as Error);
    } finally {
      setIsGenerating(false);
    }
  };

  const activeContent = generated[activeFormat];

  return (
    <div className="h-full flex">
      {/* Format Selector */}
      <div className="w-64 border-r border-white/10 p-4 space-y-2">
        <button
          onClick={generateAll}
          disabled={isGenerating}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 text-white font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-50 mb-4"
        >
          {isGenerating ? (
            <RefreshCw size={18} className="animate-spin" />
          ) : (
            <>
              <Wand2 size={18} />
              Genera Tutti
            </>
          )}
        </button>

        {formats.map((format) => {
          const Icon = format.icon;
          const hasContent = generated[format.id];
          return (
            <button
              key={format.id}
              onClick={() => setActiveFormat(format.id)}
              className={`
                w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left
                ${
                  activeFormat === format.id
                    ? 'bg-white/10 border border-white/20'
                    : 'hover:bg-white/5'
                }
              `}
            >
              <Icon size={18} className={format.color} />
              <span className="flex-1 text-sm text-zinc-300">{format.label}</span>
              {hasContent && <CheckCircle2 size={14} className="text-emerald-400" />}
            </button>
          );
        })}
      </div>

      {/* Preview Area */}
      <div className="flex-1 p-6 overflow-auto">
        {!activeContent ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <Share2 size={48} className="text-zinc-700 mb-4" />
            <h3 className="text-xl font-semibold text-zinc-400 mb-2">Trasforma il tuo articolo</h3>
            <p className="text-zinc-500 max-w-md">
              Clicca "Genera Tutti" per trasformare automaticamente il tuo articolo in contenuti
              ottimizzati per ogni piattaforma.
            </p>
          </div>
        ) : activeFormat === 'twitter' ? (
          <div className="max-w-lg mx-auto space-y-4">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Twitter size={20} className="text-sky-400" />
              Twitter/X Thread Preview
            </h3>
            {activeContent.map((tweet: string, i: number) => (
              <GlassCard key={i} className="p-4">
                <div className="flex gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-pink-500" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-white text-sm">Tu</span>
                      <span className="text-zinc-500 text-sm">@tuoaccount</span>
                    </div>
                    <p className="text-zinc-300 text-sm whitespace-pre-wrap">{tweet}</p>
                    <div className="flex gap-6 mt-3 text-zinc-500">
                      <MessageCircle size={16} />
                      <Repeat2 size={16} />
                      <Heart size={16} />
                      <Share2 size={16} />
                    </div>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        ) : activeFormat === 'linkedin' ? (
          <div className="max-w-2xl mx-auto">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Linkedin size={20} className="text-blue-400" />
              LinkedIn Post Preview
            </h3>
            <GlassCard className="p-6">
              <div className="flex gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-pink-500" />
                <div>
                  <p className="font-semibold text-white">Il Tuo Nome</p>
                  <p className="text-sm text-zinc-500">Content Marketing Specialist</p>
                  <p className="text-xs text-zinc-600">2h • 🌐</p>
                </div>
              </div>
              <p className="text-zinc-300 whitespace-pre-wrap text-sm leading-relaxed">
                {activeContent}
              </p>
            </GlassCard>
          </div>
        ) : activeFormat === 'instagram' ? (
          <div className="max-w-4xl mx-auto">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Instagram size={20} className="text-pink-400" />
              Instagram Carousel Preview
            </h3>
            <div className="grid grid-cols-5 gap-4">
              {(activeContent as InstagramSlide[]).map((slide, i: number) => (
                <GlassCard
                  key={i}
                  className="aspect-square p-4 flex flex-col items-center justify-center text-center"
                >
                  <span className="text-xs text-zinc-500 mb-2">Slide {slide.slide}</span>
                  <p className="text-white font-semibold text-sm mb-2">{slide.content}</p>
                  <p className="text-xs text-zinc-400">{slide.subtitle}</p>
                </GlassCard>
              ))}
            </div>
          </div>
        ) : activeFormat === 'tiktok' ? (
          <div className="max-w-2xl mx-auto">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Video size={20} className="text-rose-400" />
              TikTok Script Preview
            </h3>
            <GlassCard className="p-6">
              <pre className="text-zinc-300 whitespace-pre-wrap text-sm leading-relaxed font-sans">
                {activeContent}
              </pre>
            </GlassCard>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <BookOpen size={20} className="text-emerald-400" />
              Newsletter Snippet Preview
            </h3>
            <GlassCard className="p-6">
              <div className="prose prose-invert prose-sm max-w-none">
                <pre className="text-zinc-300 whitespace-pre-wrap font-sans leading-relaxed">
                  {activeContent}
                </pre>
              </div>
            </GlassCard>
          </div>
        )}
      </div>
    </div>
  );
};

// ============ PUBLISH HUB ============
const PublishHub = () => {
  const calendarEvents = useStore(store, (s) => s.calendarEvents);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);

  const days = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'];
  const currentMonth = 'Febbraio 2026';

  // Generate calendar days
  const calendarDays = Array.from({ length: 28 }, (_, i) => {
    const day = i + 1;
    const dateStr = `2026-02-${String(day).padStart(2, '0')}`;
    const events = calendarEvents.filter((e) => e.date === dateStr);
    return { day, date: dateStr, events };
  });

  const platformIcons: Record<string, LucideIcon> = {
    blog: FileText,
    twitter: Twitter,
    linkedin: Linkedin,
    instagram: Instagram,
  };

  const queue = [
    {
      id: 1,
      title: 'Thread AI Marketing',
      platform: 'twitter',
      scheduledFor: '14:00',
    },
    {
      id: 2,
      title: 'Post LinkedIn',
      platform: 'linkedin',
      scheduledFor: '16:30',
    },
  ];

  const platforms = [
    { name: 'Twitter/X', connected: true, followers: '12.4K' },
    { name: 'LinkedIn', connected: true, followers: '8.2K' },
    { name: 'Instagram', connected: false, followers: '-' },
    { name: 'Newsletter', connected: true, subscribers: '3.1K' },
  ];

  const handlePublish = () => {
    setShowConfetti(true);
    setTimeout(() => setShowConfetti(false), 100);
  };

  return (
    <div className="h-full flex">
      <Confetti trigger={showConfetti} />

      {/* Calendar */}
      <div className="flex-1 p-6 border-r border-white/10">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-white">{currentMonth}</h3>
          <div className="flex gap-2">
            <button className="p-2 rounded-lg hover:bg-white/10">
              <ChevronDown size={16} className="text-zinc-400 rotate-90" />
            </button>
            <button className="p-2 rounded-lg hover:bg-white/10">
              <ChevronDown size={16} className="text-zinc-400 -rotate-90" />
            </button>
          </div>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 gap-2 mb-2">
          {days.map((day) => (
            <div key={day} className="text-center text-xs text-zinc-500 py-2">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid grid-cols-7 gap-2">
          {calendarDays.map(({ day, date, events }) => {
            const isToday = day === 2;
            const hasEvents = events.length > 0;

            return (
              <div
                key={day}
                onClick={() => setSelectedDate(date)}
                className={`
                  aspect-square rounded-xl p-2 cursor-pointer transition-all
                  ${isToday ? 'bg-violet-500/20 border border-violet-500/50' : 'hover:bg-white/5'}
                  ${selectedDate === date ? 'ring-2 ring-violet-500' : ''}
                `}
              >
                <span
                  className={`text-sm ${isToday ? 'text-violet-300 font-semibold' : 'text-zinc-400'}`}
                >
                  {day}
                </span>
                {hasEvents && (
                  <div className="mt-1 space-y-1">
                    {events.slice(0, 2).map((event, i) => {
                      const Icon = platformIcons[event.platform] || FileText;
                      return (
                        <div
                          key={i}
                          className={`
                          flex items-center gap-1 px-1.5 py-0.5 rounded text-xs
                          ${event.status === 'scheduled' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}
                        `}
                        >
                          <Icon size={10} />
                          <span className="truncate">{event.title.slice(0, 8)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 p-4 space-y-4 overflow-auto">
        {/* Queue */}
        <GlassCard className="p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <Clock size={16} className="text-amber-400" />
            In coda
          </h3>

          <div className="space-y-2">
            {queue.map((item) => {
              const Icon = platformIcons[item.platform] || FileText;
              return (
                <div key={item.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
                  <Icon size={16} className="text-zinc-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{item.title}</p>
                    <p className="text-xs text-zinc-500">Oggi alle {item.scheduledFor}</p>
                  </div>
                  <button
                    onClick={handlePublish}
                    className="p-2 rounded-lg bg-violet-500/20 hover:bg-violet-500/30 transition-colors"
                  >
                    <Send size={14} className="text-violet-400" />
                  </button>
                </div>
              );
            })}
          </div>
        </GlassCard>

        {/* Platform Status */}
        <GlassCard className="p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <Share2 size={16} className="text-cyan-400" />
            Piattaforme
          </h3>

          <div className="space-y-2">
            {platforms.map((platform, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
                <div
                  className={`w-2 h-2 rounded-full ${platform.connected ? 'bg-emerald-400' : 'bg-zinc-600'}`}
                />
                <div className="flex-1">
                  <p className="text-sm text-white">{platform.name}</p>
                  <p className="text-xs text-zinc-500">
                    {platform.followers || platform.subscribers}
                  </p>
                </div>
                {!platform.connected && (
                  <button className="text-xs text-violet-400 hover:text-violet-300">
                    Connetti
                  </button>
                )}
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Analytics Preview */}
        <GlassCard className="p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <BarChart3 size={16} className="text-emerald-400" />
            Performance (7 giorni)
          </h3>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-400">Impressioni</span>
              <span className="text-sm text-white font-medium">24.3K</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-400">Engagement</span>
              <span className="text-sm text-emerald-400 font-medium">+12.4%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-400">Click</span>
              <span className="text-sm text-white font-medium">1.2K</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-zinc-400">Nuovi follower</span>
              <span className="text-sm text-violet-400 font-medium">+89</span>
            </div>
          </div>

          {/* Mini chart */}
          <div className="mt-4 h-16 flex items-end gap-1">
            {[40, 65, 45, 80, 55, 70, 90].map((h, i) => (
              <div
                key={i}
                className="flex-1 rounded-t bg-gradient-to-t from-violet-500 to-pink-500 opacity-80"
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

// ============ MAIN APP ============
export default function DreamThinkingRoom() {
  const activeZone = useStore(store, (s) => s.activeZone);
  const focusMode = useStore(store, (s) => s.focusMode);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
      if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
        if (focusMode) store.setState((s: StoreState) => ({ ...s, focusMode: false }));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [focusMode]);

  const renderZone = () => {
    switch (activeZone) {
      case 'inspiration':
        return <InspirationCorner />;
      case 'composer':
        return <ArticleComposer />;
      case 'research':
        return <ResearchScraper />;
      case 'social':
        return <SocialTransformer />;
      case 'publish':
        return <PublishHub />;
      default:
        return <ArticleComposer />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#e4e4e7] overflow-hidden">
      <StoreSubscriber />
      {/* Background gradient */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl" />
      </div>

      <TopBar />
      <ZoneNav />

      <main
        className={`
        h-screen pt-20 transition-all duration-500
        ${focusMode ? 'pl-0' : 'pl-20'}
      `}
      >
        {renderZone()}
      </main>

      <CommandPalette open={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />

      {/* Focus mode exit hint */}
      {focusMode && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-white/10 backdrop-blur text-sm text-zinc-400 animate-pulse">
          Premi <kbd className="px-1.5 py-0.5 bg-white/10 rounded mx-1">ESC</kbd> per uscire dal
          Focus Mode
        </div>
      )}

      {/* Custom styles */}
      <style>{`
        @keyframes confetti {
          0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
          }
        }

        .animate-confetti {
          animation: confetti 3s ease-out forwards;
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        ::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.2);
        }

        /* Prose styling for editor */
        .prose p {
          margin-bottom: 1em;
        }
        .prose h1, .prose h2, .prose h3 {
          margin-top: 1.5em;
          margin-bottom: 0.5em;
        }
      `}</style>
    </div>
  );
}
