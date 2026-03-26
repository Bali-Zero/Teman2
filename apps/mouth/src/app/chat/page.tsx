"use client";

import React from "react";
import { Loader2 } from "lucide-react";

// Il nostro "Orchestratore" della logica di business
import { useChatPage } from "@/hooks/useChatPage";

// Componenti UI puri (Stateless / Presentational)
import {
  ChatHeader,
  ChatSidebar,
  ChatMessageListVirtualized,
  ChatInputBar,
  ImageGenModal,
  Toast
} from "@/components/chat";

export default function ChatPage() {
  // 1. Estrazione di tutto lo stato e i metodi dall'Orchestratore
  const {
    displayMessages,
    isInitialLoading,
    userName,
    userAvatar,
    toast,
    isPending,
    imageModalOpen,
    messagesEndRef,
    fileInputRef,
    chatInput,
    sidebar,
    conversations,
    teamStatus,
    showUserMenu,
    handleSend,
    handleNewChat,
    handleConversationClick,
    handleDeleteConversation,
    handleImageGenSubmit,
    handleAvatarChange,
    toggleClock,
    showToast,
    setShowUserMenu,
    setImageModalOpen
  } = useChatPage();

  // 2. Gestione dello stato di caricamento iniziale (Blocking UI)
  if (isInitialLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--background)] text-white">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  }

  // 3. Rendering Puramente Dichiarativo
  return (
    <div className="flex h-screen bg-[var(--background)] text-white overflow-hidden">
      
      <ChatSidebar
        isOpen={sidebar.sidebarOpen}
        onClose={sidebar.closeSidebar}
        conversations={conversations.conversations}
        currentConversationId={conversations.currentConversationId}
        isLoading={conversations.isLoading}
        onConversationClick={handleConversationClick}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        onSearchDocsOpen={sidebar.openSearchDocs}
      />

      <div className="flex flex-col flex-1 min-w-0">
        <ChatHeader
          isSidebarOpen={sidebar.sidebarOpen}
          onToggleSidebar={sidebar.toggleSidebar}
          isClockIn={teamStatus.isClockIn}
          isClockLoading={teamStatus.isLoading}
          onToggleClock={toggleClock}
          messagesCount={displayMessages.length}
          isWsConnected={true} 
          userName={userName}
          userAvatar={userAvatar}
          showUserMenu={showUserMenu}
          onToggleUserMenu={() => setShowUserMenu(!showUserMenu)}
          userMenuRef={null as any}
          avatarInputRef={null as any}
          onAvatarUpload={handleAvatarChange}
          onShowToast={showToast}
        />

        <ChatMessageListVirtualized
          messages={displayMessages as any}
          isLoading={isPending}
          isInitialLoading={isInitialLoading}
          thinkingElapsedTime={0} // Deleghiamo il processing interno
          userAvatar={userAvatar}
          messagesEndRef={messagesEndRef}
          onFollowUpClick={(q) => { 
            chatInput.setInput(q); 
            handleSend(); 
          }}
          onSetInput={chatInput.setInput}
          onOpenSearchDocs={sidebar.openSearchDocs}
        />

        <ChatInputBar
          input={chatInput.input}
          setInput={chatInput.setInput}
          isLoading={isPending}
          showImagePrompt={chatInput.imageGenPrompt !== ""}
          setShowImagePrompt={(val) => chatInput.setImageGenPrompt(val ? " " : "")}
          onSend={handleSend}
          onImageGenerate={() => setImageModalOpen(true)}
          showAttachMenu={false}
          setShowAttachMenu={() => {}}
          attachMenuRef={null as any}
          fileInputRef={fileInputRef}
          onFileChange={async (e) => chatInput.handleImageAttach(e)}
          isRecording={false}
          recordingTime={0}
          onStartRecording={() => {}}
          onStopRecording={() => {}}
        />
      </div>

      <ImageGenModal
        isOpen={imageModalOpen}
        onClose={() => setImageModalOpen(false)}
        onSubmit={(prompt) => {
          chatInput.setImageGenPrompt(prompt);
          handleImageGenSubmit();
        }}
      />

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => showToast("", "success")} // Hack pulito per chiudere il toast
        />
      )}
    </div>
  );
}
