function distance(a, b) {
    return Math.pow(a.lat - b.lat, 2) + Math.pow(a.lng - b.lng, 2);
}


function formatAttrString(str) {
    str = str.replace(/(_[a-z])/g, (match) => match[1].toUpperCase());

    // Split the string at the first uppercase letter after the first character
    let parts = str.match(/^[a-z]+|[A-Z][a-z]*/g);
    
    if (parts) {
        // Capitalize the first word, make everything else lowercase
        return parts.map((part, index) => 
            index === 0 ? part.charAt(0).toUpperCase() + part.slice(1).toLowerCase() : part.toLowerCase()
        ).join(' ');
    }
    
    return str;
}
