document.getElementById('fetch-data').addEventListener('click', fetchData);
document.getElementById('scrape-data').addEventListener('click', scrapeAndFetchData);

async function fetchData() {
    const groupByCheckboxes = document.querySelectorAll('#group-by input[type="checkbox"]');
    const selectedOptions = Array.from(groupByCheckboxes).filter(checkbox => checkbox.checked).map(checkbox => checkbox.value);
    const groupBy = selectedOptions.join('&group_by=');
    const minCount = document.getElementById('min-count').value;
    const searchUrl = document.getElementById('search-url').value;

    const baseUrl = 'http://0.0.0.0:8000';
    const url = `${baseUrl}/cars/grouped?min_count=${minCount}&group_by=${groupBy}&search_url=${encodeURIComponent(searchUrl)}`;

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

async function scrapeAndFetchData() {
    const searchUrl = document.getElementById('search-url').value;
    const baseUrl = 'http://0.0.0.0:8000';

    // Step 1: POST to /ads
    try {
        const postResponse = await fetch(`${baseUrl}/ads`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ search_url: searchUrl })
        });
        if (!postResponse.ok) {
            throw new Error(`HTTP error! status: ${postResponse.status}`);
        }
    } catch (error) {
        console.error('Failed to scrape data:', error);
        return;
    }

    // Step 2: GET to /cars/grouped
    await fetchData();
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

        // yearRange
        let yearRange;
        if (group.cars.length === 1 || minYear === maxYear) {
            yearRange = minYear;
        } else {
            yearRange = `${minYear}-${maxYear}`;
        }

        const priceRange = (minPrice === maxPrice) ? `EUR ${minPrice}` : `EUR ${minPrice} - ${maxPrice}`;

        const groupHeader = document.createElement('h2');
        groupHeader.innerText = `${group.make} ${group.model} ${yearRange} (${group.count}) - ${priceRange}`;
        groupDiv.appendChild(groupHeader);

        const img = document.createElement('img');
        img.src = group.cars[0].img_src;
        groupDiv.appendChild(img);

        const toggleButton = document.createElement('button');
        toggleButton.innerText = 'Show/Hide Cars';
        groupDiv.appendChild(toggleButton);

        const sortSelect = document.createElement('select');
        const sortOptions = [
            { value: 'price', text: 'Price' },
            { value: 'year', text: 'Year' }
        ];
        sortOptions.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.text = option.text;
            sortSelect.appendChild(opt);
        });

        const carList = document.createElement('ul');
        carList.className = 'car-list hidden';
        groupDiv.appendChild(carList);

        toggleButton.addEventListener('click', () => {
            carList.classList.toggle('hidden');
        });

        sortSelect.addEventListener('change', () => {
            const sortBy = sortSelect.value;
            const sortedCars = [...group.cars].sort((a, b) => sortBy === 'price' ? a.price - b.price : a.year - b.year);
            updateCarList(carList, sortedCars);
        });

        // Default sorting
        const sortedCars = [...group.cars].sort((a, b) => a.price - b.price);
        updateCarList(carList, sortedCars);

        groupDiv.appendChild(sortSelect);

        resultsDiv.appendChild(groupDiv);
    });
}

function updateCarList(carList, cars) {
    carList.innerHTML = '';
    cars.forEach(car => {
        const carItem = document.createElement('li');
        const carLink = document.createElement('a');
        carLink.href = "https://www.polovniautomobili.com" + car.link;
        carLink.target = "_blank";
        carLink.innerText = `${car.make} ${car.model} - ${car.year} (${car.engine_capacity}cm3) - EUR ${car.price}`;
        carItem.appendChild(carLink);
        carList.appendChild(carItem);
    });
}
