// articles/ChapterPage.jsx
import React, { useContext } from 'react';
import BookContext from './BookContext';
import { useParams } from 'react-router-dom';

const ChapterPage = () => {
    const { currentState } = useContext(BookContext);
    const { chapterId } = useParams();

    // Simulate fetching content based on the URL parameter and stored state
    const currentContent = currentState.chapterData[chapterId] || "Chapter not found.";

    return (
        <div className="book-page">
            <h2 aria-live="polite">Chapter {chapterId}: The Deep Dive</h2>
            <p>This chapter page dynamically reads content from the BookContext, simulating a multi-page book experience.</p>
            <div className="book-content" style={{ border: '1px solid #ccc', padding: '20px' }}>
                <strong>Content Loaded successfully for Chapter {chapterId}:</strong>
                <p>{currentContent}</p>
            </div>
        </div>
    );
};

export default ChapterPage;