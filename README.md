# RetoMotors

## Help Assistant

El asistente de ayuda está disponible únicamente dentro de la aplicación autenticada. Usa documentación curada del proyecto y búsqueda Full Text de PostgreSQL para recuperar contexto antes de generar una respuesta breve con GPT-5 Nano.

Es una ayuda de solo lectura: no consulta leads, clientes ni conversaciones en vivo, no ejecuta SQL, no tiene herramientas ni puede modificar datos. No guarda preguntas ni respuestas. La clave `OPENAI_API_KEY` vive únicamente en la Edge Function; el frontend no necesita ni recibe una clave de OpenAI.

Para cargar la documentación en `app.help_knowledge`:

```bash
uv run load-help-knowledge
```

La Edge Function se despliega posteriormente con `supabase functions deploy help-chat`. Configura en el entorno server-side `OPENAI_API_KEY` y, opcionalmente, `HELP_CHAT_MODEL=gpt-5-nano`.

