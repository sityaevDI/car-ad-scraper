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

        // Рассчитываем диапазон лет и цен
        const years = group.cars.map(car => car.year);
        const prices = group.cars.map(car => car.price);
        const minYear = Math.min(...years);
        const maxYear = Math.max(...years);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);

        const yearRange = (group.year !== undefined) ? group.year : `${minYear}-${maxYear}`;
        const priceRange = (minPrice === maxPrice) ? `EUR ${minPrice}` : `EUR ${minPrice} - EUR ${maxPrice}`;

        const groupHeader = document.createElement('h2');
        groupHeader.innerText = `${group.make} ${group.model} ${yearRange} (${group.count})`;
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

        const sortSelect = document.createElement('select');
        const sortOptions = [
            { value: 'year', text: 'Year' },
            { value: 'price', text: 'Price' }
        ];
        sortOptions.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.text = option.text;
            sortSelect.appendChild(opt);
        });

        sortSelect.addEventListener('change', () => {
            const sortedCars = [...group.cars];
            const sortBy = sortSelect.value;
            sortedCars.sort((a, b) => sortBy === 'price' ? a.price - b.price : a.year - b.year);
            updateCarList(carList, sortedCars);
        });

        groupDiv.appendChild(sortSelect);

        const carList = document.createElement('ul');
        carList.className = 'car-list hidden';
        updateCarList(carList, group.cars);

        groupDiv.appendChild(carList);

        resultsDiv.appendChild(groupDiv);
    });
}

function updateCarList(carList, cars) {
    carList.innerHTML = '';
    cars.forEach(car => {
        const carItem = document.createElement('li');
        const carLink = document.createElement('a');
        carLink.href = "https://www.polovniautomobili.com" + car.link;
        carLink.innerText = `${car.make} ${car.model} - ${car.year} (${car.engine_capacity}) - EUR ${car.price}`;
        carItem.appendChild(carLink);
        carList.appendChild(carItem);
    });
}
