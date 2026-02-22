"use client";

import React from "react";
import {
  User,
  Mail,
  Phone,
  MapPin,
  Globe,
  Edit2,
  MessageCircle,
  CreditCard,
  Plane,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function TestClientPage() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">
          Layout /clients/[id] - 3 Colonne
        </h1>

        {/* 3 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* COL 1: Client Info + WhatsApp Avatar */}
          <div className="space-y-4">
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b">
                <h3 className="font-semibold">Client Info</h3>
                <div className="flex items-center gap-2">
                  {/* AVATAR LEADER - CLICCABILE WHATSAPP */}
                  <a
                    href="https://wa.me/628123456789"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 group"
                    title="Message Damar on WhatsApp"
                  >
                    <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center ring-2 ring-green-500/30 group-hover:ring-green-500 transition-all">
                      <User className="w-4 h-4 text-green-500" />
                    </div>
                    <MessageCircle className="w-3.5 h-3.5 text-green-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </a>
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                    <Edit2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>

              <div className="p-4 space-y-3">
                <div className="flex items-start gap-2">
                  <User className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs text-muted-foreground">Full Name</p>
                    <p className="text-sm font-medium">Marco Rossi</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Mail className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs text-muted-foreground">Email</p>
                    <p className="text-sm">marco.rossi@example.com</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Phone className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs text-muted-foreground">Phone</p>
                    <p className="text-sm">+39 333 123 4567</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Globe className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs text-muted-foreground">Nationality</p>
                    <p className="text-sm">Italian</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs text-muted-foreground">Address</p>
                    <p className="text-sm">Jl. Pantai Batu Bolong, Canggu</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* COL 2: Passport */}
          <div className="rounded-xl border bg-card overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b">
              <CreditCard className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">Passport</h3>
              <span className="ml-auto px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400">
                M
              </span>
            </div>
            <div className="p-4">
              <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-border bg-muted/50 flex items-center justify-center mb-4">
                <div className="text-center">
                  <CreditCard className="w-12 h-12 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">
                    Passport document
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Number:</span>
                  <span className="font-mono">YA123456</span>
                </div>
                <div className="bg-yellow-500/20 border border-yellow-500/50 rounded-lg p-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-yellow-700 dark:text-yellow-400">
                      Expiry:
                    </span>
                    <span className="font-semibold text-yellow-700 dark:text-yellow-400">
                      15 Aug 2026
                    </span>
                  </div>
                  <p className="text-[10px] text-yellow-700 dark:text-yellow-400 mt-1">
                    ⚠️ 5 months - Contact embassy
                  </p>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">DOB:</span>
                  <span>20 Mar 1985</span>
                </div>
              </div>
            </div>
          </div>

          {/* COL 3: Visa */}
          <div className="rounded-xl border bg-card overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b">
              <CreditCard className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">Actual Visa</h3>
            </div>
            <div className="p-4">
              <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-border bg-muted/50 flex items-center justify-center mb-4">
                <div className="text-center">
                  <Plane className="w-12 h-12 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">KITAS (ITAS)</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Type:</span>
                  <span className="font-medium">KITAS (ITAS)</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Start:</span>
                  <span>1 Feb 2025</span>
                </div>
                <div className="bg-green-500/20 border border-green-500/30 rounded-lg p-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-green-700 dark:text-green-400">
                      Exp Visa:
                    </span>
                    <span className="font-semibold text-green-700 dark:text-green-400">
                      1 Feb 2026
                    </span>
                  </div>
                </div>
                <div className="flex justify-between text-sm p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <span className="text-muted-foreground">Days remaining:</span>
                  <span className="font-semibold text-green-600">349 days</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-6 text-sm text-muted-foreground">
          👆 Clicca sull'avatar verde in alto a destra della colonna "Client
          Info" per aprire WhatsApp
        </p>
      </div>
    </div>
  );
}
