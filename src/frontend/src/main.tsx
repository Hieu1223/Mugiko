import React from 'react'
import ReactDOM from 'react-dom/client'
import {
  LookupProvider,
  SessionProvider,
  ToastProvider,
} from '@mugiko/common'
import { App } from './App'
import '../packages/common/src/styles/base.css'

const page = document.body.dataset.page || 'home'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <SessionProvider>
      <ToastProvider>
        <LookupProvider>
          <App page={page} />
        </LookupProvider>
      </ToastProvider>
    </SessionProvider>
  </React.StrictMode>,
)
