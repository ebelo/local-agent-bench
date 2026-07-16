// articles/BookContext.js
import React, { createContext, useState, useMemo } from 'react';

const BookContext = createContext();

export const BookProvider = ({ children }) => {
    const [currentState, setCurrentState] = useState({
        currentPageId: 1,
        totalPages: 3,
        chapterData: {
            1: "The beginning of the story.",
            2: "Rising action and conflict introduction.",
            3: "The resolution/climax."
        }
    });

    const setCurrentPage = (pageId) => {
        setCurrentState(prev => ({ ...prev, currentPageId: pageId }));
    };

    const contextValue = useMemo(() => ({
        currentState,
        setCurrentPage
    }), [currentState]);

    return (
        <BookContext.Provider value={contextValue}>
            {children}
        </BookContext.Provider>
    );
};

export default BookContext;