"use client"

import React from 'react'
import { FileText, CheckCircle, Clock, AlertTriangle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Document {
    id: string
    filename: string
    status: string
    type: string | null
    confidence: number | null
    processed_at: string | null
    entities?: {
        expedientes?: string[]
        quejosos?: string[]
        tribunales?: string[]
        [key: string]: string[] | undefined
    }
}

interface DocumentListProps {
    documents: Document[]
    isLoading: boolean
}

export function DocumentList({ documents, isLoading }: DocumentListProps) {

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'indexado':
                return <CheckCircle className="w-4 h-4 text-green-500" />
            case 'error':
                return <AlertTriangle className="w-4 h-4 text-red-500" />
            case 'procesando':
            case 'ocr_ok':
            case 'normalizado':
            case 'clasificado':
                return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
            default:
                return <Clock className="w-4 h-4 text-slate-500" />
        }
    }

    const getStatusLabel = (status: string) => {
        // Map raw status to user friendly label
        const map: Record<string, string> = {
            'indexado': 'Listo',
            'error': 'Error',
            'procesando': 'Procesando...',
            'ocr_ok': 'OCR Completado',
            'normalizado': 'Normalizado',
            'clasificado': 'Clasificado',
            'pending': 'Pendiente'
        }
        return map[status] || status
    }

    if (isLoading) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="w-8 h-8 text-primary animate-spin" />
            </div>
        )
    }

    if (documents.length === 0) {
        return (
            <div className="text-center p-8 text-slate-500 border border-dashed border-slate-700 rounded-lg">
                No hay documentos procesados.
            </div>
        )
    }

    return (
        <div className="space-y-2">
            {documents.map((doc) => (
                <div
                    key={doc.id}
                    className="group flex items-center justify-between p-4 bg-slate-800/50 border border-slate-700/50 rounded-lg hover:bg-slate-800 transition-all hover:border-primary/30"
                >
                    <div className="flex items-center space-x-4">
                        <div className="p-2 bg-slate-900 rounded-lg">
                            <FileText className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h4 className="font-medium text-slate-200">{doc.filename}</h4>
                            <div className="flex items-center space-x-2 text-xs text-slate-400 mt-1">
                                <span className="capitalize">{doc.type?.replace(/_/g, ' ') || 'Desconocido'}</span>
                                {doc.confidence !== null && (
                                    <span>• {(doc.confidence * 100).toFixed(0)}% confianza</span>
                                )}
                            </div>
                            {doc.entities && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {doc.entities.expedientes?.slice(0, 1).map((exp, i) => (
                                        <span key={i} className="text-[9px] px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded border border-blue-800/40">
                                            📋 {exp}
                                        </span>
                                    ))}
                                    {doc.entities.quejosos?.slice(0, 1).map((q, i) => (
                                        <span key={i} className="text-[9px] px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded border border-purple-800/40">
                                            👤 {q.length > 30 ? q.slice(0, 30) + '…' : q}
                                        </span>
                                    ))}
                                    {doc.entities.tribunales?.slice(0, 1).map((t, i) => (
                                        <span key={i} className="text-[9px] px-1.5 py-0.5 bg-amber-900/40 text-amber-300 rounded border border-amber-800/40">
                                            ⚖️ {t.length > 35 ? t.slice(0, 35) + '…' : t}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-xs font-medium">
                        {getStatusIcon(doc.status)}
                        <span className={cn(
                            doc.status === 'indexado' ? "text-green-500" :
                                doc.status === 'error' ? "text-red-500" : "text-slate-400"
                        )}>
                            {getStatusLabel(doc.status)}
                        </span>
                    </div>
                </div>
            ))}
        </div>
    )
}
