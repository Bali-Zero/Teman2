import React from 'react';
import { motion } from 'framer-motion';
import { PricingResponse, PricingCategory, PricingItem } from '@/types/pricing';
import { Info, AlertTriangle, MessageCircle } from 'lucide-react';

interface PricingTableProps {
  data: PricingResponse;
}

const containerVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { 
      duration: 0.5, 
      staggerChildren: 0.1 
    } 
  }
};

const itemVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: { opacity: 1, x: 0 }
};

export const PricingTable: React.FC<PricingTableProps> = ({ data }) => {
  if (data.error) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-200 text-sm flex items-center gap-2">
        <AlertTriangle size={16} />
        {data.error}
      </div>
    );
  }

  const renderPrice = (item: PricingItem) => {
    if (item.price) return <span className="text-xl font-bold text-white">{item.price}</span>;
    if (item.price_1y && item.price_2y) {
      return (
        <div className="flex flex-col">
          <span className="text-lg font-bold text-white">{item.price_1y} <span className="text-xs font-normal text-white/50">(1y)</span></span>
          <span className="text-lg font-bold text-white">{item.price_2y} <span className="text-xs font-normal text-white/50">(2y)</span></span>
        </div>
      );
    }
    if (item.offshore || item.onshore) {
      return (
        <div className="flex flex-col gap-1">
          {item.offshore && <span className="text-lg font-bold text-emerald-400">{item.offshore} <span className="text-xs font-normal text-white/50">(Offshore)</span></span>}
          {item.onshore && <span className="text-lg font-bold text-blue-400">{item.onshore} <span className="text-xs font-normal text-white/50">(Onshore)</span></span>}
        </div>
      );
    }
    return <span className="text-white/60 text-sm">Contact for Quote</span>;
  };

  const renderCategory = (title: string, items: PricingCategory | undefined) => {
    if (!items || Object.keys(items).length === 0) return null;

    return (
      <motion.div variants={itemVariants} className="mb-6 last:mb-0">
        <h3 className="text-sm font-medium text-white/40 uppercase tracking-widest mb-3 pl-1 border-l-2 border-emerald-500/50">
          {title.replace(/_/g, ' ')}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(items).map(([name, details]) => (
            <div 
              key={name} 
              className="group relative overflow-hidden rounded-xl border border-white/5 bg-white/5 p-4 hover:bg-white/10 transition-colors"
            >
              <div className="absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                 <Info size={14} className="text-white/30" />
              </div>
              
              <h4 className="font-semibold text-white/90 mb-1 leading-tight">{name}</h4>
              
              {/* If it's a search result, it might be nested differently, adapt if needed */}
              <div className="mt-2 text-right">
                {renderPrice(details)}
              </div>

              {details.notes && (
                <div className="mt-2 text-xs text-white/50 border-t border-white/5 pt-2">
                  {details.notes}
                </div>
              )}
            </div>
          ))}
        </div>
      </motion.div>
    );
  };

  // Combine search results if present
  const renderContent = () => {
    if (data.results) {
      // It's a search result
      return Object.entries(data.results).map(([category, items]) => 
        renderCategory(category, items as PricingCategory)
      );
    }

    // It's a specific category listing
    return (
      <>
        {renderCategory("Single Entry Visas", data.single_entry_visas)}
        {renderCategory("Multiple Entry Visas", data.multiple_entry_visas)}
        {renderCategory("KITAS & Long Stay", data.kitas_permits)}
        {renderCategory("Business & Legal", data.business_legal_services)}
        {renderCategory("Taxation", data.taxation_services)}
        {renderCategory("Quick Packages", data.quick_quotes)}
      </>
    );
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="w-full my-4 rounded-2xl bg-black/40 backdrop-blur-md border border-white/10 overflow-hidden shadow-2xl"
    >
      {/* Header */}
      <div className="px-5 py-3 bg-white/5 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
           <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
           <span className="text-xs font-bold text-white/70 uppercase tracking-widest">
             {data.official_notice?.replace('🔒 ', '') || 'Official Pricing'}
           </span>
        </div>
        {data.search_query && (
          <span className="text-xs text-white/40 italic">
            Search: &quot;{data.search_query}&quot;
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-5">
        {renderContent()}

        {/* Warnings */}
        {data.important_warnings && Object.keys(data.important_warnings).length > 0 && (
          <div className="mt-6 p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
             <h4 className="text-xs font-bold text-orange-400 uppercase mb-2 flex items-center gap-2">
               <AlertTriangle size={12} /> Important Warnings
             </h4>
             <ul className="space-y-1">
               {Object.values(data.important_warnings).map((warning, i) => (
                 <li key={i} className="text-xs text-orange-200/80 flex items-start gap-2">
                   <span className="mt-1 w-1 h-1 rounded-full bg-orange-500/50 shrink-0" />
                   {warning}
                 </li>
               ))}
             </ul>
          </div>
        )}

        {/* Contact Footer */}
        {data.contact_info && (
          <div className="mt-6 flex items-center justify-between pt-4 border-t border-white/5">
             <div className="text-xs text-white/40">
               Official Pricing 2025 • Subject to change
             </div>
             <a 
               href={`https://wa.me/${data.contact_info.whatsapp?.replace(/[^0-9]/g, '')}`}
               target="_blank"
               rel="noopener noreferrer"
               className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 text-xs font-medium transition-colors cursor-pointer"
             >
               <MessageCircle size={12} />
               Contact Support
             </a>
          </div>
        )}
      </div>
    </motion.div>
  );
};
