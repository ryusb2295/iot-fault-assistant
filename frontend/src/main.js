import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@fontsource/ibm-plex-sans-kr/korean-400.css'
import '@fontsource/ibm-plex-sans-kr/korean-500.css'
import '@fontsource/ibm-plex-sans-kr/korean-600.css'
import '@fontsource/ibm-plex-sans-kr/korean-700.css'
import '@fontsource/ibm-plex-sans-kr/latin-400.css'
import '@fontsource/ibm-plex-sans-kr/latin-500.css'
import '@fontsource/ibm-plex-sans-kr/latin-600.css'
import '@fontsource/ibm-plex-sans-kr/latin-700.css'
import './assets/main.css'

const app = createApp(App)

app.use(router)
app.use(ElementPlus)

app.mount('#app')
