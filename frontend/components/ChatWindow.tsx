"use client"

import React, { useState, useRef, useEffect } from 'react'
import { Send, User, Bot, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'

interface Message {
    role: 'user' | 'assistant'
    content: string
}

export function ChatWindow() {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: 'Hola, soy Gomas AI. ¿En qué puedo ayudarte con tus documentos legales?' }
    ])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages, isLoading])

    const handleSend = async () => {
        if (!input.trim() || isLoading) return

        const userMessage = input
        setInput('')
        setMessages(prev => [...prev, { role: 'user', content: userMessage }])
        setIsLoading(true)

        try {
            // We query all documents (doc_ids: null)
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
            const response = await fetch(`${apiUrl}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userMessage, doc_ids: null }),
            })

            if (!response.ok) {
                throw new Error("Error en la consulta")
            }

            const data = await response.json()
            setMessages(prev => [...prev, { role: 'assistant', content: data.answer }])
        } catch (error) {
            setMessages(prev => [...prev, { role: 'assistant', content: "Lo siento, hubo un error al procesar tu consulta." }])
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="flex flex-col h-[600px] w-full bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden shadow-2xl backdrop-blur-sm">
            {/* Header */}
            <div className="p-4 border-b border-slate-700 bg-slate-900/80">
                <h3 className="font-semibold text-slate-200">Chat Assistant</h3>
                <p className="text-xs text-slate-400">Powered by Gomas Engine</p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
                {messages.map((msg, idx) => (
                    <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={cn(
                            "flex w-full",
                            msg.role === 'user' ? "justify-end" : "justify-start"
                        )}
                    >
                        <div className={cn(
                            "max-w-[80%] rounded-2xl p-4 text-sm shadow-md",
                            msg.role === 'user'
                                ? "bg-primary text-white"
                                : "bg-slate-800 text-slate-200 border border-slate-700"
                        )}>
                            {msg.content}
                        </div>
                    </motion.div>
                ))}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-slate-800 text-slate-200 border border-slate-700 rounded-2xl p-4 flex items-center space-x-2">
                            <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            <span className="text-xs text-slate-400">Analizando documentos...</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="p-4 bg-slate-900/80 border-t border-slate-700 flex gap-2">
                <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Escribe tu pregunta jurídica..."
                    className="flex-1 bg-slate-950 border-slate-700 text-slate-200 focus-visible:ring-primary"
                />
                <Button onClick={handleSend} disabled={isLoading} className="bg-primary hover:bg-primary/90 text-white">
                    <Send className="w-4 h-4" />
                </Button>
            </div>
        </div>
    )
}
