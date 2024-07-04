let makesAndModels = null;
const baseUrl = 'http://localhost:8000';

document.getElementById('fetch-data').addEventListener('click', fetchData);
document.getElementById('scrape-data').addEventListener('click', scrapeAndFetchData);
document.getElementById('add-include-filter').addEventListener('click', () => addFilter('include-filters'));
document.getElementById('add-exclude-filter').addEventListener('click', () => addFilter('exclude-filters'));

async function fetchData() {
    const groupByCheckboxes = document.querySelectorAll('#group-by input:checked');
    const groupBy = Array.from(groupByCheckboxes).map(checkbox => checkbox.value);
    const minCount = document.getElementById('min-count').value;

    const includeFilters = getFilters('include-filters');
    const excludeFilters = getFilters('exclude-filters');
    const searchUrl = document.getElementById('search-url').value;

    const url = new URL(`${baseUrl}/cars/grouped`);
    url.searchParams.append('min_count', minCount);
    for (gb_param in groupBy) {
        url.searchParams.append('group_by', groupBy[gb_param]);
    }
    url.searchParams.append('search_url', searchUrl);

    if (includeFilters) {
        url.searchParams.append('makes_to_include', JSON.stringify(includeFilters));
    }
    if (excludeFilters) {
        url.searchParams.append('makes_to_exclude', JSON.stringify(excludeFilters));
    }
    if (searchUrl) {
        url.searchParams.append('search_url', searchUrl);
    }

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

    try {
        const response = await fetch(`${baseUrl}/ads`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ search_url: searchUrl })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Fetch data after scraping
        fetchData();
    } catch (error) {
        console.error('Failed to scrape data:', error);
    }
}

function getFilters(containerId) {
    const filters = {};
    const filterContainers = document.querySelectorAll(`#${containerId} .filter-container`);
    filterContainers.forEach(container => {
        const make = container.querySelector('.make-select').value;
        const models = $(container.querySelector('.model-select')).val();
        if (make) {
            filters[make] = models;
        }
    });
    return Object.keys(filters).length ? filters : null;
}

function addFilter(containerId) {
    if (!makesAndModels) {
        fetchMakesAndModels(() => addFilter(containerId));
        return;
    }

    const container = document.getElementById(containerId);
    const filterContainer = document.createElement('div');
    filterContainer.className = 'filter-container';

    const makeSelect = document.createElement('select');
    makeSelect.className = 'make-select';
    makeSelect.innerHTML = '<option value="">Select Make</option>';
    for (const make in makesAndModels) {
        const option = document.createElement('option');
        option.value = make;
        option.text = make;
        makeSelect.appendChild(option);
    }

    const modelSelect = document.createElement('select');
    modelSelect.className = 'model-select';
    modelSelect.disabled = true;
    modelSelect.multiple = true;

    makeSelect.addEventListener('change', () => {
        populateModels(makeSelect, modelSelect);
        validateMakeSelections(containerId);
    });

    const removeButton = document.createElement('button');
    removeButton.innerText = 'Remove';
    removeButton.addEventListener('click', () => {
        filterContainer.remove();
        validateMakeSelections(containerId);
    });

    filterContainer.appendChild(makeSelect);
    filterContainer.appendChild(modelSelect);
    filterContainer.appendChild(removeButton);
    container.appendChild(filterContainer);

    // Initialize Select2 on the modelSelect element
    $(modelSelect).select2();
}

async function fetchMakesAndModels(callback) {

    try {
        const response = await fetch(`${baseUrl}/cars/makes`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        makesAndModels = await response.json();
        if (callback) callback();
    } catch (error) {
        console.error('Failed to fetch makes and models:', error);
    }
}

function populateModels(makeSelect, modelSelect) {
    const selectedMake = makeSelect.value;
    if (!selectedMake) {
        modelSelect.disabled = true;
        $(modelSelect).empty();
        return;
    }

    const models = makesAndModels[selectedMake] || [];
    $(modelSelect).empty();
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.text = model;
        modelSelect.appendChild(option);
    });
    modelSelect.disabled = false;
}

function displayResults(groups) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '';

    // Sort groups by count
    groups.sort((a, b) => b.count - a.count);

    groups.forEach(group => {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'group';

        // Calculate year and price ranges
        const years = group.cars.map(car => car.year);
        const prices = group.cars.map(car => car.price);
        const minYear = Math.min(...years);
        const maxYear = Math.max(...years);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);

        let yearRange;
        if (group.cars.length === 1 || minYear === maxYear) {
            yearRange = minYear; // if there's only one car or all cars have the same year
        } else {
            yearRange = `${minYear}-${maxYear}`;
        }

        const priceRange = (minPrice === maxPrice) ? `EUR ${minPrice}` : `EUR ${minPrice} - EUR ${maxPrice}`;

        const groupHeader = document.createElement('h2');
        const make = group.make || group.makes[0];

        const model = group.model || '';
        groupHeader.innerText = `${make} ${model ? model + ' ' : ''}${yearRange} (${group.count}) - ${priceRange}`;

        groupDiv.appendChild(groupHeader);

        const img = document.createElement('img');
        img.src = group.cars[0].img_src;
        groupDiv.appendChild(img);

        const toggleButton = document.createElement('button');
        toggleButton.innerText = 'Show/Hide Cars';
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

        // Default sorting by year
        const sortedCars = [...group.cars].sort((a, b) => a.year - b.year);
        updateCarList(carList, sortedCars);

        groupDiv.appendChild(sortSelect);

        resultsDiv.appendChild(groupDiv);
    });
}

function validateMakeSelections(containerId) {
    const makeSelects = document.querySelectorAll(`#${containerId} .make-select`);
    const selectedMakes = Array.from(makeSelects).map(select => select.value);
    makeSelects.forEach(select => {
        const currentValue = select.value;
        Array.from(select.options).forEach(option => {
            if (option.value !== currentValue && selectedMakes.includes(option.value)) {
                option.disabled = true;
            } else {
                option.disabled = false;
            }
        });
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

// Initialize Select2 on page load
$(document).ready(function() {
    $('.make-select').select2();
    $('.model-select').select2();
});
