const gallery = document.getElementById("gallery");
const viewer = document.getElementById("viewer");
const full = document.getElementById("full");

// 🔥 загрузка всех фото при старте
async function loadImages() {
    try {
        const res = await fetch("/images");
        const images = await res.json();

        images.forEach(name => addImageToGallery(name));
    } catch (e) {
        console.error("Ошибка загрузки изображений:", e);
    }
}

// 🔥 добавление одной картинки (динамически)
function addImageToGallery(name, prepend = true) {
    const div = document.createElement("div");
    div.className = "skeleton"; // skeleton эффект

    const img = document.createElement("img");
    img.dataset.name = name;

    img.onload = () => div.replaceWith(img);
    img.onerror = () => {
        console.warn("Не удалось загрузить:", name);
        div.remove();
    };

    img.src = `/image?name=${encodeURIComponent(name)}`;
    img.onclick = () => {
        full.src = img.src;
        viewer.style.display = "flex";
    };

    if (prepend) {
        gallery.prepend(div); // новые сверху
    } else {
        gallery.appendChild(div);
    }
}

// 🔥 закрытие просмотрщика
function closeViewer() {
    viewer.style.display = "none";
    full.src = "";
}

// 🔥 загрузка новых изображений после upload
async function handleUpload(form) {
    const formData = new FormData(form);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });
        const data = await res.json();

        if (data.status === "ok") {
            addImageToGallery(data.name); // добавляем только новую картинку
        } else {
            alert("Ошибка загрузки: " + (data.error || "неизвестная ошибка"));
        }
    } catch (e) {
        console.error("Upload error:", e);
        alert("Ошибка загрузки");
    }
}

// 🔥 событие формы загрузки
const uploadForm = document.getElementById("uploadForm");
if (uploadForm) {
    uploadForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleUpload(uploadForm);
    });
}

document.addEventListener("DOMContentLoaded", loadImages);