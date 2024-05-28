document.getElementById('fetch-data').addEventListener('click', fetchData);

async function fetchData() {
    const groupBySelect = document.getElementById('group-by');
    const selectedOptions = Array.from(groupBySelect.selectedOptions).map(option => option.value);
    const groupBy = selectedOptions.join('&group_by=');
    const minCount = document.getElementById('min-count').value;

    const baseUrl = 'http://0.0.0.0:8000';
    const url = `${baseUrl}/cars/grouped?min_count=${minCount}&group_by=${groupBy}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        displayResults(data);
    } catch (error) {
        console.error('Failed to fetch data:', error);
    }
}

function displayResults(groups) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '';

    // Сортировка групп по count
    groups.sort((a, b) => b.count - a.count);

    groups.forEach(group => {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'group';

        const groupHeader = document.createElement('h2');
        groupHeader.innerText = `${group.make} ${group.model} ${group.year} (${group.count})`;
        groupDiv.appendChild(groupHeader);

        const img = document.createElement('img');
        img.src = group.cars[0].img_src;
        groupDiv.appendChild(img);

        const toggleButton = document.createElement('button');
        toggleButton.innerText = 'Show/Hide Cars';
        toggleButton.addEventListener('click', () => {
            carList.classList.toggle('hidden');
        });
        groupDiv.appendChild(toggleButton);

        const carList = document.createElement('ul');
        carList.className = 'car-list hidden'; // Добавляем скрытый класс по умолчанию
        group.cars.forEach(car => {
            const carItem = document.createElement('li');
            const carLink = document.createElement('a');
            carLink.href = "https://www.polovniautomobili.com" + car.link;
            carLink.innerText = `${car.make} ${car.model} - ${car.year} - EUR ${car.price}`;
            carItem.appendChild(carLink);
            carList.appendChild(carItem);
        });
        groupDiv.appendChild(carList);

        resultsDiv.appendChild(groupDiv);
    });
}
