"use client"

import { useState, useEffect } from 'react'
import { UploadZone } from '@/components/UploadZone'
import { DocumentList } from '@/components/DocumentList'
import { ChatWindow } from '@/components/ChatWindow'
import { LayoutDashboard, MessageSquare } from 'lucide-react'

export default function Home() {
  const [documents, setDocuments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'chat'>('dashboard')

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_URL}/documents`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
      }
    } catch (e) {
      console.error("Failed to fetch docs", e)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    // Initial load
    fetchDocuments()

    // Use SSE for real-time updates (replaces 5-second polling)
    let eventSource: EventSource | null = null
    let fallbackInterval: ReturnType<typeof setInterval> | null = null

    const startFallbackPolling = () => {
      if (!fallbackInterval) {
        fallbackInterval = setInterval(fetchDocuments, 5000)
      }
    }

    try {
      eventSource = new EventSource(`${API_URL}/events`)
      eventSource.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data)
          if (Array.isArray(payload.documents)) {
            setDocuments(payload.documents)
            setIsLoading(false)
          }
        } catch (_) {}
      }
      eventSource.onerror = () => {
        eventSource?.close()
        eventSource = null
        startFallbackPolling()
      }
    } catch (_) {
      startFallbackPolling()
    }

    return () => {
      eventSource?.close()
      if (fallbackInterval) clearInterval(fallbackInterval)
    }
  }, [])

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <header className="flex items-center justify-between mb-12 animate-fade-in">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Gomas Legal Engine
          </h1>
          <p className="text-slate-400">Inteligencia Artificial para Análisis Jurídico</p>
        </div>

        <div className="flex p-1 bg-slate-900/50 backdrop-blur rounded-lg border border-slate-800">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'dashboard' ? 'bg-primary text-white shadow-lg' : 'text-slate-400 hover:text-white'
              }`}
          >
            <LayoutDashboard className="w-4 h-4 mr-2" />
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === 'chat' ? 'bg-primary text-white shadow-lg' : 'text-slate-400 hover:text-white'
              }`}
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            Assistant
          </button>
        </div>
      </header>

      {activeTab === 'dashboard' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-fade-in">
          {/* Left Column: Upload */}
          <div className="lg:col-span-1 space-y-8">
            <section className="glass-panel p-6 rounded-2xl">
              <h2 className="text-xl font-semibold mb-4 text-slate-200">Subir Documentos</h2>
              <UploadZone onUploadComplete={fetchDocuments} />
            </section>

            <section className="glass-panel p-6 rounded-2xl">
              <h2 className="text-xl font-semibold mb-2 text-slate-200">Estado del Sistema</h2>
              <div className="grid grid-cols-2 gap-4 mt-4">
                <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800">
                  <div className="text-2xl font-bold text-primary">{documents.length}</div>
                  <div className="text-xs text-slate-500">Documentos</div>
                </div>
                <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800">
                  <div className="text-2xl font-bold text-green-500">
                    {documents.filter((d: any) => d.status === 'indexado').length}
                  </div>
                  <div className="text-xs text-slate-500">Indexados</div>
                </div>
              </div>
            </section>
          </div>

          {/* Right Column: List */}
          <div className="lg:col-span-2">
            <section className="glass-panel p-6 rounded-2xl h-full">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-slate-200">Documentos Procesados</h2>
                <button onClick={fetchDocuments} className="text-xs text-primary hover:underline">
                  Actualizar
                </button>
              </div>
              <DocumentList documents={documents} isLoading={isLoading} />
            </section>
          </div>
        </div>
      ) : (
        <div className="max-w-4xl mx-auto animate-fade-in">
          <ChatWindow />
        </div>
      )}
    </div>
  )
}
