function distance(a, b) {
    return Math.pow(a.lat - b.lat, 2) + Math.pow(a.lng - b.lng, 2);
}


function formatAttrString(str) {
    str = str.replace(/(_[a-z])/g, (match) => match[1].toUpperCase());

    let parts = str.match(/^[a-z]+|[A-Z][a-z]*/g);
    
    if (parts) {
        // Capitalize the first word, make everything else lowercase
        return parts.map((part, index) => 
            index === 0 ? part.charAt(0).toUpperCase() + part.slice(1).toLowerCase() : part.toLowerCase()
        ).join(' ');
    }
    
    return str;
}


function getOctodirectionalArrow(angle) {
    const arrows = ['↑', '↗', '→', '↘', '↓', '↙', '←', '↖'];
    const normalizedAngle = ((angle % 360) + 360) % 360;
    const index = Math.round(normalizedAngle / 45) % 8;
    return arrows[index];
}


function shuffle(array) {
    let currentIndex = array.length, randomIndex;
    while (currentIndex != 0) {
        randomIndex = Math.floor(Math.random() * currentIndex);
        currentIndex--;
        [array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
    }
    return array;
}