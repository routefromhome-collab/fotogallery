const gallery = document.getElementById("gallery");
const viewer = document.getElementById("viewer");
const full = document.getElementById("full");

let loadedImages = new Set(); // Чтобы не дублировать картинки

// Функция подгрузки всех изображений
async function loadImages() {
    try {
        const res = await fetch("/images");
        const images = await res.json();

        images.forEach(name => {
            if (loadedImages.has(name)) return; // Уже загружено
            loadedImages.add(name);

            const div = document.createElement("div");
            div.className = "skeleton";
            gallery.appendChild(div);

            const img = document.createElement("img");
            img.dataset.name = name;
            img.onload = () => div.replaceWith(img);
            img.onerror = () => {
                div.className = "error";
                div.textContent = "Ошибка загрузки";
            };
            img.src = `/image?name=${encodeURIComponent(name)}`;
            img.onclick = () => {
                full.src = img.src;
                viewer.style.display = "flex";
            }
        });
    } catch (err) {
        console.error("Ошибка загрузки изображений:", err);
    }
}

// Функция закрытия полноэкранного просмотра
function closeViewer() {
    viewer.style.display = "none";
    full.src = "";
}

// Подгрузка новых изображений после добавления
async function uploadAndAdd(fileInput) {
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (data.status !== "ok") {
            alert("Ошибка загрузки: " + (data.error || "неизвестная"));
            return;
        }

        // Добавляем только что загруженное фото
        const name = data.name;
        if (!loadedImages.has(name)) {
            loadedImages.add(name);

            const div = document.createElement("div");
            div.className = "skeleton";
            gallery.appendChild(div);

            const img = document.createElement("img");
            img.dataset.name = name;
            img.onload = () => div.replaceWith(img);
            img.onerror = () => {
                div.className = "error";
                div.textContent = "Ошибка загрузки";
            };
            img.src = `/image?name=${encodeURIComponent(name)}`;
            img.onclick = () => {
                full.src = img.src;
                viewer.style.display = "flex";
            }
        }

    } catch (err) {
        console.error("Ошибка загрузки файла:", err);
        alert("Ошибка загрузки файла");
    } finally {
        fileInput.value = ""; // Очистка input
    }
}

// Подключаем загрузку после загрузки DOM
document.addEventListener("DOMContentLoaded", () => {
    loadImages();

    const uploadInput = document.querySelector("input[name=file]");
    uploadInput.addEventListener("change", () => uploadAndAdd(uploadInput));
});
