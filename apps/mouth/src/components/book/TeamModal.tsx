'use client';

import * as Dialog from '@radix-ui/react-dialog';
import { LazyMotion, domAnimation, m, AnimatePresence } from 'framer-motion';
import Image from 'next/image';
import { X } from 'lucide-react';
import type { TeamMember } from './book-data';
import { CONTACTS } from './book-data';

interface TeamModalProps {
  member: TeamMember | null;
  open: boolean;
  onClose: () => void;
}

export function TeamModal({ member, open, onClose }: TeamModalProps) {
  return (
    <LazyMotion features={domAnimation}>
      <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50" />
          <Dialog.Content className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-4">
            <AnimatePresence>
              {open && member && (
                <m.div
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 40 }}
                  transition={{ duration: 0.3 }}
                  className="bg-[#161618] border border-white/10 rounded-2xl p-8 w-full max-w-md relative"
                >
                  <Dialog.Close asChild>
                    <button className="absolute top-4 right-4 text-white/40 hover:text-white transition-colors">
                      <X size={20} />
                    </button>
                  </Dialog.Close>

                  <div className="flex items-center gap-5 mb-6">
                    {member.photo ? (
                      <Image
                        src={member.photo}
                        alt={member.name}
                        width={72}
                        height={72}
                        className="rounded-full object-cover w-[72px] h-[72px]"
                      />
                    ) : (
                      <div className="w-[72px] h-[72px] rounded-full bg-[#d4845a]/20 flex items-center justify-center text-[#d4845a] font-bold text-xl font-[family-name:var(--font-spartan)]">
                        {member.name.slice(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <Dialog.Title className="font-[family-name:var(--font-spartan)] text-xl font-bold text-white">
                        {member.name}
                      </Dialog.Title>
                      <p className="text-[#d4845a] text-sm font-[family-name:var(--font-montserrat)]">
                        {member.role}
                      </p>
                    </div>
                  </div>

                  <a
                    href={`${CONTACTS.whatsappUrl}?text=Ciao, vorrei parlare con ${encodeURIComponent(member.name)} del team Bali Zero`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full text-center py-3 bg-[#25D366] text-white rounded-xl font-[family-name:var(--font-montserrat)] font-medium hover:bg-[#1fb855] transition-colors"
                  >
                    Contatta via WhatsApp
                  </a>
                </m.div>
              )}
            </AnimatePresence>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </LazyMotion>
  );
}
