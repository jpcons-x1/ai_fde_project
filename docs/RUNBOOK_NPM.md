# Ejecutar UnderCover y comprobarlo

Este documento registra los pasos realizados en este repositorio y el procedimiento para instalar dependencias, validar las pruebas y arrancar la aplicación en Windows PowerShell.

## Requisitos del proyecto

- Node.js compatible con `package.json`: `^22.22.2 || ^24.15.0 || >=26.0.0`.
- Python 3.12 y `uv`.
- Un archivo `.env` configurado para ejecutar la aplicación. No se debe compartir ni copiar su contenido en logs o documentación.

En esta sesión se detectaron Node.js `v24.15.0` y npm `12.2.1`. `npm run check` reportó Python `3.12.12`.

## Comandos ejecutados y resultados

Se ejecutaron los siguientes comandos desde la raíz del repositorio:

1. Comprobar versiones y cambios locales:

   ```powershell
   git status --short
   npm --version
   node --version
   ```

   Node y npm estaban dentro del rango declarado en el proyecto. El árbol de trabajo estaba limpio antes de las operaciones de npm.

2. Instalar paquetes de Node:

   ```powershell
   npm install
   ```

   La instalación terminó correctamente. El script `prepare` instaló los hooks de Lefthook y Chromium de Playwright. npm informó 21 vulnerabilidades: 15 moderadas, 4 altas y 2 críticas. Una auditoría con vulnerabilidades no significa que la instalación o las pruebas hayan fallado.

3. Ejecutar todas las comprobaciones antes de modificar dependencias:

   ```powershell
   npm run check
   ```

   Resultado: éxito. Ruff y Pyright pasaron; pasaron 158 pruebas Python, 33 pruebas TypeScript y 7 pruebas end-to-end.

4. Consultar el detalle de las alertas:

   ```powershell
   npm audit
   ```

   El informe identificó dependencias transitivas vulnerables. Algunas correcciones requerían cambios incompatibles si se usaba `npm audit fix --force`.

5. Aplicar solo actualizaciones que npm ofrecía sin `--force`:

   ```powershell
   npm audit fix
   ```

   El comando terminó y el número de vulnerabilidades bajó a 15 moderadas. Actualizó `package-lock.json`; ese archivo quedó modificado.

6. La repetición de `npm run check` después de actualizar las dependencias fue denegada y no se ejecutó. Por tanto, el resultado verde de las pruebas corresponde al estado anterior a `npm audit fix`. Antes de dar por validado el estado actual, hay que ejecutar de nuevo:

   ```powershell
   npm run check
   ```

## Preparar y probar una instalación

Desde la carpeta raíz del repositorio:

1. Confirmar que estás en la raíz y revisar los cambios existentes:

   ```powershell
   Get-Location
   git status --short
   ```

2. Instalar o sincronizar las dependencias Python:

   ```powershell
   uv sync
   ```

3. Instalar las dependencias Node y preparar Lefthook y Playwright:

   ```powershell
   npm install
   ```

   En una instalación normal, revisa los mensajes de `npm audit`. No uses automáticamente `npm audit fix --force`: puede introducir cambios incompatibles. Conserva los cambios existentes del lockfile y no los descartes sin autorización.

4. Ejecutar todos los checks:

   ```powershell
   npm run check
   ```

   Este comando ejecuta los checks Python, los checks TypeScript y los tests end-to-end. Los tests están diseñados para usar SQLite, un modelo de prueba y servicios sustitutos; no requieren una llamada al modelo ni leen `.env`.

5. Si el propósito es solo validar el repositorio, termina aquí. No es necesario arrancar servicios ni ejecutar `npm run seed`.

## Arrancar la aplicación

Para ejecutar el producto, primero crea y configura `.env` localmente. Según `docs/TECH_STACK.md`, las variables relevantes incluyen `OPENROUTER_API_KEY`, `DATABASE_URL` y las claves de Langfuse. No escribas sus valores en este runbook, no los pegues en el chat y no los incluyas en la salida de comandos.

La aplicación y el agente necesitan una base de datos configurada en `DATABASE_URL`; el agente guarda allí el estado de su trabajo. Comprueba que `.env` existe sin imprimir su contenido:

```powershell
Test-Path .env
```

Inicia los servicios:

```powershell
npm run dev
```

El comando inicia el backend en `http://localhost:8000`, el servicio del agente en el puerto `8002` y el dashboard en `http://localhost:5173`. Abre el dashboard en el navegador para usar la aplicación.

### Sembrar los datos de nuevo

Solo si necesitas reconstruir la base de datos que usa `npm run dev`, ejecuta:

```powershell
npm run seed
```

Esto restablece los datos de claims desde `data/`; no es un paso requerido para cada inicio. Confirma que quieres reiniciar esos datos antes de ejecutarlo.

## Diagnóstico breve

- Si `npm install` termina con avisos de auditoría pero sin error de instalación, las dependencias se instalaron; consulta las pruebas con `npm run check` por separado.
- Si falla un check, conserva la salida completa y corrige el fallo antes de arrancar la aplicación.
- Si las pruebas pasan pero la aplicación no arranca, comprueba que `.env` esté presente y correctamente configurado sin mostrar sus secretos.
- Después de cualquier cambio de dependencias, vuelve a ejecutar `npm run check`.
- No uses `npm audit fix --force` como solución automática. Evalúa por separado la actualización mayor requerida y ejecuta los checks después de cualquier cambio.
