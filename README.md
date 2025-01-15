# jocarsa | lightsteelblue

![LightSteelBlue Logo](https://jocarsa.com/static/logo/jocarsa%20%7C%20LightSteelBlue.svg)


**Author:** Jose Vicente Carratala Sanchis  
**Repository:** [https://github.com/jocarsa/jocarsa-lightsteelblue](https://github.com/jocarsa/jocarsa-lightsteelblue)

## Introducción

**jocarsa | lightsteelblue** es un navegador de imágenes mejorado desarrollado en Python. Esta aplicación proporciona una interfaz gráfica intuitiva para explorar, visualizar y gestionar tus colecciones de fotos en formato JPG/JPEG. Con funcionalidades avanzadas como ajuste de exposición, selección y recorte de imágenes, y renombrado basado en datos EXIF, **lightsteelblue** es la herramienta perfecta para fotógrafos y entusiastas que buscan una solución eficiente y personalizable para manejar sus imágenes.

## Instalación

### Requisitos Previos

Asegúrate de tener [Python 3.7+](https://www.python.org/downloads/) instalado en tu sistema.

### Clonar el Repositorio

```bash
git clone https://github.com/jocarsa/jocarsa-lightsteelblue.git
cd jocarsa-lightsteelblue
```

### Crear un Entorno Virtual (Opcional pero Recomendado)

```bash
python -m venv venv
```

Activar el entorno virtual:

- **Windows:**

  ```bash
  venv\Scripts\activate
  ```

- **macOS/Linux:**

  ```bash
  source venv/bin/activate
  ```

### Instalar Dependencias

```bash
pip install -r requirements.txt
```

**Nota:** Si `requirements.txt` no está presente, puedes instalar las dependencias manualmente:

```bash
pip install numpy exifread pillow ttkbootstrap
```

## Dependencias

El proyecto utiliza las siguientes librerías de Python:

- **Tkinter:** Biblioteca estándar para interfaces gráficas en Python.
- **ttkbootstrap:** Temas mejorados para Tkinter que proporcionan una apariencia moderna y personalizable.
- **Pillow:** Biblioteca de procesamiento de imágenes.
- **ExifRead:** Para extraer metadatos EXIF de las imágenes.
- **NumPy:** Optimiza los ajustes de exposición de las imágenes.
- **Threading:** Para la generación de miniaturas en segundo plano.

## Guía de Usuario

### Inicio de la Aplicación

Ejecuta el siguiente comando en tu terminal o símbolo del sistema:

```bash
python lightsteelblue.py
```

### Interfaz de Usuario

La aplicación está dividida en varias secciones:

- **Barra de Herramientas Superior:**
  - **Seleccionar carpeta:** Permite elegir la carpeta que contiene tus imágenes JPG/JPEG.
  - **Copiar imagen:** Copia la imagen actual a la carpeta de selección con las modificaciones aplicadas.
  - **Config:** Abre la ventana de configuración para personalizar los atajos de teclado.

- **Columnas Principales:**
  - **Izquierda:** Árbol de directorios que muestra las imágenes en la carpeta seleccionada.
  - **Centro:** Canvas que muestra la imagen actual. Permite ajustar la exposición y realizar selecciones para recorte.
  - **Derecha:** Árbol de directorios que muestra las imágenes copiadas en la carpeta de selección.

- **Barra de Estado Inferior:**
  - Muestra mensajes y el progreso de las operaciones actuales.

### Funcionalidades Principales

#### Seleccionar Carpeta

1. Haz clic en el botón **"Seleccionar carpeta"**.
2. Navega y elige la carpeta que contiene tus imágenes JPG/JPEG.
3. La aplicación cargará las imágenes y generará miniaturas en segundo plano.

#### Navegar Entre Imágenes

- **Atajos de Teclado:**
  - **Siguiente Foto:** Tecla definida en la configuración (por defecto, tecla de flecha derecha).
  - **Foto Anterior:** Tecla definida en la configuración (por defecto, tecla de flecha izquierda).

- **Uso del Árbol de Directorios:**
  - Haz clic en cualquier imagen de la lista para visualizarla en el canvas central.

#### Ajustar Exposición

- **Aumentar Exposición:** Tecla definida en la configuración (por defecto, `KP_Add`).
- **Disminuir Exposición:** Tecla definida en la configuración (por defecto, `KP_Subtract`).

#### Copiar Imagen

1. Ajusta la exposición si lo deseas.
2. (Opcional) Selecciona una región de la imagen arrastrando el cursor en el canvas central.
3. Haz clic en el botón **"Copiar imagen"** o usa el atajo de teclado configurado (por defecto, tecla `z`).
4. La imagen (o la región seleccionada) se copiará a la carpeta `seleccion` dentro de la carpeta original.

#### Configurar Atajos de Teclado

1. Haz clic en el botón **"Config"** en la barra de herramientas superior.
2. En la ventana de configuración, personaliza las teclas para las siguientes acciones:
   - Foto Anterior
   - Foto Siguiente
   - Guardar Foto
   - Aumentar Exposición
   - Disminuir Exposición
3. Haz clic en **"Guardar"** para aplicar los cambios.

#### Renombrar Imágenes Basado en EXIF

1. Haz clic en el botón **"Renombrar (EXIF)"** en la barra de herramientas inferior.
2. La aplicación renombrará todas las imágenes JPG/JPEG en la carpeta seleccionada utilizando la fecha y hora de creación almacenadas en los metadatos EXIF.
3. Si una imagen no contiene datos EXIF, se omitirá el renombrado.

### Progreso y Estado

- **Barra de Progreso:** Indica tu posición actual dentro de la colección de imágenes.
- **Barra de Estado:** Muestra mensajes sobre las operaciones en curso y cualquier error o notificación importante.

### Generación de Miniaturas

La aplicación genera miniaturas para cada imagen en segundo plano para optimizar la navegación. Estas miniaturas se almacenan en la subcarpeta `miniaturas` dentro de cada directorio correspondiente.

## Contribuciones

¡Las contribuciones son bienvenidas! Si deseas mejorar esta aplicación, por favor sigue estos pasos:

1. Haz un fork del repositorio.
2. Crea una nueva rama (`git checkout -b feature/nueva-funcionalidad`).
3. Realiza tus cambios y haz commits descriptivos.
4. Envía tu rama a GitHub (`git push origin feature/nueva-funcionalidad`).
5. Abre un Pull Request detallando tus mejoras.

## Licencia

Este proyecto está licenciado bajo la [Licencia MIT](LICENSE).

## Contacto

**Jose Vicente Carratala Sanchis**  
Correo electrónico: [josevicente@example.com](mailto:info@josevicentecarratala.com)  
GitHub: [https://github.com/jocarsa](https://github.com/jocarsa)

---

¡Gracias por usar **jocarsa | lightsteelblue**! Esperamos que esta herramienta mejore tu experiencia en la gestión de tus imágenes.
